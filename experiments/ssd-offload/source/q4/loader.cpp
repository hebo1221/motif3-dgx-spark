#include "ggml.h"
#include "ggml-backend.h"
#include <dlfcn.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>
#include <list>
#include <unordered_map>
#include <set>
#include <thread>
#include <atomic>
#include <chrono>
#include <fstream>
#include <array>
#include <mutex>
#include <sstream>
#include <filesystem>
#include <sys/file.h>
#include <sys/statvfs.h>
#include <cerrno>
#include <algorithm>

static bool q4_target(int l){return l>=2&&l<=52;}
static void q4_prefetch(int,const int32_t*,size_t);
static void *q4_storage[53][3]{};
static std::unordered_map<int,std::array<std::vector<char>,3>> q4_entries;
static uintptr_t model_base=0;
static size_t model_length=0;
static int model_fd=-1;
static bool enabled=false,fast=false;
static std::vector<char> startup_staging;
static uint64_t startup_copies=0,startup_bytes=0,startup_verified=0,startup_read_ns=0,startup_upload_ns=0;
extern "C" void motif_startup_stats(uint64_t *out){uint64_t values[]={startup_copies,startup_bytes,startup_verified,startup_read_ns,startup_upload_ns};memcpy(out,values,sizeof values);}

static std::atomic<uint64_t> timing[8];
using TimerClock=std::chrono::steady_clock;
struct Timer {int index;TimerClock::time_point begin=TimerClock::now();Timer(int i):index(i){}~Timer(){timing[index]+=std::chrono::duration_cast<std::chrono::nanoseconds>(TimerClock::now()-begin).count();}};
extern "C" void motif_profile(uint64_t *out){for(int i=0;i<8;i++)out[i]=timing[i];}
extern "C" void motif_fast(int value){fast=value;}
static int read_workers=4;
extern "C" void motif_workers(int n){if(n!=4&&n!=8&&n!=16)abort();read_workers=n;}

static bool target_fd(int fd){char link[64],path[4096];snprintf(link,sizeof link,"/proc/self/fd/%d",fd);auto n=readlink(link,path,sizeof(path)-1);if(n<0)return false;path[n]=0;const char *wanted=getenv("MOTIF_SOURCE");return wanted&&strcmp(path,wanted)==0;}
extern "C" void *mmap(void *addr,size_t len,int prot,int flags,int fd,off_t off){
    using Fn=void*(*)(void*,size_t,int,int,int,off_t);static auto real=(Fn)dlsym(RTLD_NEXT,"mmap");
    bool target=target_fd(fd);if(target)flags&=~MAP_POPULATE;
    void *p=real(addr,len,prot,flags,fd,off);
    if(target&&p!=MAP_FAILED){if(off!=0||model_base){fprintf(stderr,"Unexpected model mapping\n");abort();}model_base=(uintptr_t)p;model_length=len;model_fd=dup(fd);fprintf(stderr,"MOTIF_LAZY_MMAP bytes=%zu\n",len);}
    return p;
}
extern "C" void *mmap64(void *addr,size_t len,int prot,int flags,int fd,off64_t off){return mmap(addr,len,prot,flags,fd,(off_t)off);}
extern "C" int posix_madvise(void *addr,size_t len,int advice){
    using Fn=int(*)(void*,size_t,int);static auto real=(Fn)dlsym(RTLD_NEXT,"posix_madvise");
    uintptr_t p=(uintptr_t)addr;if(model_base&&p>=model_base&&p-model_base<model_length&&advice==POSIX_MADV_WILLNEED)return 0;
    return real(addr,len,advice);
}
constexpr size_t EXP_BYTES=10485760;
static std::atomic<uint64_t> disk_hits{0},disk_bytes{0},source_bytes{0},prefault_sink{0};
static std::mutex pad_mutex;
static std::unordered_map<uint64_t,std::array<char,512>> saved_padding;
static void check_disk_identity(){
    static bool checked=false;if(checked)return;checked=true;
    const char *root=getenv("MOTIF_NVME_CACHE");if(!root)return;
    std::ifstream in(std::string(root)+"/source.identity");uint64_t bytes,mtime;struct stat st;
    if(!(in>>bytes>>mtime)||fstat(model_fd,&st)||bytes!=(uint64_t)st.st_size||mtime!=(uint64_t)st.st_mtim.tv_sec*1000000000+st.st_mtim.tv_nsec){fprintf(stderr,"NVMe source identity mismatch\n");abort();}
}
static bool disk_read_root(char *out,size_t n,uint64_t offset,const char *root){
    if(!root)return false;
    if(n==512){std::lock_guard<std::mutex> lock(pad_mutex);auto it=saved_padding.find(offset);if(it!=saved_padding.end()){memcpy(out,it->second.data(),512);return true;}return false;}
    if(n!=EXP_BYTES)return false;
    std::string prefix=std::string(root)+"/"+std::to_string(offset);std::ifstream digest(prefix+".sha256");std::string expected;
    if(!(digest>>expected))return false;
    int fd=open((prefix+".bin").c_str(),O_RDONLY);struct stat st;
    if(fd<0||fstat(fd,&st)||st.st_size<(off_t)n||st.st_size>(off_t)(n+512)){fprintf(stderr,"NVMe payload missing or invalid\n");abort();}
    std::vector<unsigned char> storage;if(!fast)storage.resize(st.st_size);unsigned char *bytes=fast?(unsigned char*)out:storage.data();size_t length=st.st_size;
    {Timer io(2);size_t done=0;while(done<length){ssize_t got=pread(fd,bytes+done,length-done,done);if(got<=0)abort();done+=got;}}close(fd);
    using Sha=unsigned char*(*)(const unsigned char*,size_t,unsigned char*);
    static void *lib=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL);static Sha sha=lib?(Sha)dlsym(lib,"SHA256"):nullptr;
    unsigned char hash[32];{Timer hashing(3);if(!sha||!sha(bytes,length,hash))abort();}char hex[65];for(int i=0;i<32;i++)snprintf(hex+i*2,3,"%02x",hash[i]);
    if(expected!=hex){fprintf(stderr,"NVMe SHA256 mismatch at %llu\n",(unsigned long long)offset);abort();}
    if(!fast){Timer copying(4);memcpy(out,bytes,n);}
    if(length==n+512){std::array<char,512> padding;memcpy(padding.data(),bytes+n,512);std::lock_guard<std::mutex> lock(pad_mutex);saved_padding[offset+n]=padding;}
    disk_hits++;disk_bytes+=length;return true;
}
// Bounded admission cache. Published base entries are never modified or evicted.
static int dynamic_mode=0;
static std::atomic<uint64_t> overlay_hits{0},overlay_writes{0},overlay_bytes{0},overlay_skips{0},overlay_write_ns{0};
static uint64_t charged_file(const std::filesystem::path &p){struct stat st;if(lstat(p.c_str(),&st)||!S_ISREG(st.st_mode))return 0;return ((std::max(uint64_t(st.st_size),uint64_t(st.st_blocks)*512)+4095)/4096)*4096;}
struct Overlay {
    std::string root;int lock_fd=-1,dir_fd=-1;uint64_t used=0,cap=160ull*1024*1024*1024,floor=64ull*1024*1024*1024;
    std::mutex mutex;
    Overlay(){
        const char *r=getenv("MOTIF_DYNAMIC_CACHE");if(!r||!*r){fprintf(stderr,"Missing dynamic cache root\n");abort();}root=r;
        const char *base=getenv("MOTIF_NVME_CACHE");if(!base||std::filesystem::equivalent(root,base)){fprintf(stderr,"Overlay must differ from base\n");abort();}
        if(const char *v=getenv("MOTIF_DYNAMIC_CAP_BYTES"))cap=std::stoull(v);
        if(cap>160ull*1024*1024*1024)abort();
        if(const char *v=getenv("MOTIF_DYNAMIC_FLOOR_BYTES"))floor=std::stoull(v);
        if(floor<64ull*1024*1024*1024||floor>(1ull<<62))abort();
        lock_fd=open((root+"/.writer.lock").c_str(),O_CREAT|O_RDWR|O_NOFOLLOW,0600);
        if(lock_fd<0||flock(lock_fd,LOCK_EX|LOCK_NB)){fprintf(stderr,"Dynamic cache already in use or lock failed\n");abort();}
        dir_fd=open(root.c_str(),O_RDONLY|O_DIRECTORY);if(dir_fd<0)abort();
        std::ifstream id(root+"/source.identity");uint64_t size,mtime;struct stat st;
        if(!(id>>size>>mtime)||fstat(model_fd,&st)||size!=(uint64_t)st.st_size||mtime!=(uint64_t)st.st_mtim.tv_sec*1000000000+st.st_mtim.tv_nsec){fprintf(stderr,"Overlay source identity mismatch\n");abort();}
        for(const auto &entry:std::filesystem::directory_iterator(base))used+=charged_file(entry.path());
        for(const auto &entry:std::filesystem::directory_iterator(root))used+=charged_file(entry.path());
    }
};
static Overlay &overlay(){static Overlay value;return value;}
extern "C" void motif_dynamic(int mode){if(mode<0||mode>2)abort();dynamic_mode=mode;if(mode){check_disk_identity();overlay();}std::lock_guard<std::mutex> lock(pad_mutex);saved_padding.clear();}
extern "C" void motif_overlay_stats(uint64_t *out){out[0]=overlay_hits;out[1]=overlay_writes;out[2]=overlay_bytes;out[3]=overlay_skips;out[4]=overlay_write_ns;out[5]=dynamic_mode?overlay().used:0;}
static std::string payload_sha(const char *data,size_t n){using Sha=unsigned char*(*)(const unsigned char*,size_t,unsigned char*);static void *lib=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL);static Sha sha=lib?(Sha)dlsym(lib,"SHA256"):nullptr;unsigned char digest[32];if(!sha||!sha((const unsigned char*)data,n,digest))abort();char hex[65];for(int i=0;i<32;i++)snprintf(hex+i*2,3,"%02x",digest[i]);return hex;}
static void fd_write_all(int fd,const char *data,size_t n){size_t done=0;while(done<n){ssize_t k=write(fd,data+done,n-done);if(k<0&&errno==EINTR)continue;if(k<=0){perror("cache write");abort();}done+=k;}}
static void overlay_store(char *data,size_t n,uint64_t offset){
    if(dynamic_mode!=1||n!=EXP_BYTES)return;auto begin=TimerClock::now();auto &c=overlay();
    // The final expert at EOF has no following transfer padding.
    if(!fast||offset>model_length||n>model_length-offset)abort();
    size_t pad_bytes=model_length-offset-n>=512?512:0;size_t length=n+pad_bytes;
    std::string prefix=c.root+"/"+std::to_string(offset);
    uint64_t cost=((length+4095)/4096)*4096+4096;
    {
        std::lock_guard<std::mutex> lock(c.mutex);struct statvfs fs;
        if(std::filesystem::exists(prefix+".sha256"))return;
        if(statvfs(c.root.c_str(),&fs)){perror("statvfs");abort();}
        uint64_t free_bytes=uint64_t(fs.f_bavail)*fs.f_frsize;
        // A full cache keeps serving originals; no deletion or global disk cleanup occurs.
        if(c.used>c.cap||cost>c.cap-c.used||free_bytes<c.floor+cost+uint64_t(read_workers)*cost){overlay_skips++;return;}
        c.used+=cost;
    }
    size_t done=0;while(done<pad_bytes){auto k=pread(model_fd,data+n+done,pad_bytes-done,offset+n+done);if(k<0&&errno==EINTR)continue;if(k<=0)abort();done+=k;}source_bytes+=pad_bytes;
    std::string hash=payload_sha(data,length),temp=prefix+".tmp."+std::to_string(getpid());
    int fd=open(temp.c_str(),O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW,0600);if(fd<0){perror("cache temp");abort();}
    fd_write_all(fd,data,length);if(fsync(fd))abort();
    std::vector<char> verify(length);done=0;while(done<length){auto k=pread(fd,verify.data()+done,length-done,done);if(k<0&&errno==EINTR)continue;if(k<=0)abort();done+=k;}
    if(payload_sha(verify.data(),length)!=hash){fprintf(stderr,"Dynamic cache write verification failed\n");abort();}
    if(fchmod(fd,0444)||close(fd)||rename(temp.c_str(),(prefix+".bin").c_str())||fsync(c.dir_fd))abort();
    std::string side=temp+".sha256";int digest_fd=open(side.c_str(),O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW,0600);if(digest_fd<0)abort();hash+='\n';fd_write_all(digest_fd,hash.data(),hash.size());
    if(fsync(digest_fd)||fchmod(digest_fd,0444)||close(digest_fd)||rename(side.c_str(),(prefix+".sha256").c_str())||fsync(c.dir_fd))abort();
    if(pad_bytes==512){std::lock_guard<std::mutex> lock(pad_mutex);std::array<char,512> pad;memcpy(pad.data(),data+n,512);saved_padding[offset+n]=pad;}
    overlay_writes++;overlay_bytes+=length;overlay_write_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(TimerClock::now()-begin).count();
}
static bool disk_read(char *out,size_t n,uint64_t offset){
    if(dynamic_mode&&disk_read_root(out,n,offset,overlay().root.c_str())){if(n==EXP_BYTES)overlay_hits++;return true;}
    return disk_read_root(out,n,offset,getenv("MOTIF_NVME_CACHE"));
}

extern "C" void motif_disk_stats(uint64_t *out){out[0]=disk_hits;out[1]=disk_bytes;out[2]=source_bytes;}

struct Entry {std::vector<char> data;std::list<uint64_t>::iterator age;};
struct Cache {
    std::unordered_map<uint64_t,Entry> entries;
    std::list<uint64_t> age;
    uint64_t offsets[53][3]{};
    size_t capacity=16ull*1024*1024*1024/EXP_BYTES;
    uint64_t hits=0,misses=0,reads=0,copies=0,copy_bytes=0,verified=0;
    std::vector<char> staging;
    Cache(){std::ifstream in("tensors.txt");int l,k;uint64_t off,n;size_t count=0;while(in>>l>>k>>off>>n){if(l<2||l>52||k<0||k>2||n!=EXP_BYTES)abort();offsets[l][k]=off;count++;}if(count!=153)abort();}
    void touch(uint64_t key){auto &e=entries.at(key);age.erase(e.age);age.push_front(key);e.age=age.begin();}
    char *insert(uint64_t key){Timer allocation(0);std::vector<char> data;
        if(fast&&entries.size()>=capacity){auto victim=age.back();data=std::move(entries.at(victim).data);entries.erase(victim);age.pop_back();}
        while(entries.size()>=capacity){entries.erase(age.back());age.pop_back();}
        if(data.empty())data.resize(EXP_BYTES+(fast?512:0));
        age.push_front(key);auto it=entries.emplace(key,Entry{std::move(data),age.begin()}).first;return it->second.data.data();}

};
static Cache &cache(){static Cache c;return c;}
static void read_exact(char *p,size_t n,uint64_t offset){fprintf(stderr,"Forbidden BF16 expert read in full-Q4 shell mode\n");abort();Timer reading(5);if(disk_read(p,n,offset))return;source_bytes+=n;size_t done=0;while(done<n){auto got=pread(model_fd,p+done,n-done,offset+done);if(got<=0){perror("expert pread");abort();}done+=got;}overlay_store(p,n,offset);}
extern "C" void motif_enable(int value){enabled=value;if(value)std::vector<char>().swap(startup_staging);fprintf(stderr,"MOTIF_CACHE enabled=%d\n",value);}
extern "C" void motif_reset(){auto &c=cache();c.entries.clear();c.age.clear();c.hits=c.misses=c.reads=c.copies=c.copy_bytes=c.verified=0;}
extern "C" void motif_stats(uint64_t *out){auto &c=cache();uint64_t v[]={c.hits,c.misses,c.reads,c.copies,c.copy_bytes,c.entries.size()*EXP_BYTES,c.verified};memcpy(out,v,sizeof v);}
extern "C" void motif_prefetch(int layer,const int32_t *ids,size_t count){
    if(!getenv("MOTIF_DIRECT_LAYER")||strcmp(getenv("MOTIF_DIRECT_LAYER"),"q4")){fprintf(stderr,"Full-Q4 shell requires Q4 replacement\n");abort();}if(layer<2||layer>52||model_fd<0)abort();if(q4_target(layer)&&getenv("MOTIF_DIRECT_LAYER")){q4_prefetch(layer,ids,count);return;}auto &c=cache();
    if(!enabled){
        if(!getenv("MOTIF_REFERENCE_PREFAULT"))return;
        std::set<int> unique;for(size_t i=0;i<count;i++){if(ids[i]<0||ids[i]>=384)abort();unique.insert(ids[i]);}
        std::vector<uint64_t> offsets;for(int id:unique)for(int k=0;k<3;k++)offsets.push_back(c.offsets[layer][k]+uint64_t(id)*EXP_BYTES);
        std::atomic<size_t> next{0};std::vector<std::thread> workers;
        for(int t=0;t<4;t++)workers.emplace_back([&](){for(;;){size_t j=next++;if(j>=offsets.size())break;auto off=offsets[j];posix_fadvise(model_fd,off,EXP_BYTES,POSIX_FADV_WILLNEED);const volatile unsigned char *p=(const volatile unsigned char*)(model_base+off);uint64_t sum=0;for(size_t i=0;i<EXP_BYTES;i+=4096)sum+=p[i];sum+=p[EXP_BYTES-1];prefault_sink+=sum;}});
        for(auto &w:workers)w.join();return;
    }
    Timer prefetch_wall(1);check_disk_identity();
    std::set<int> selected;for(size_t i=0;i<count;i++){if(ids[i]<0||ids[i]>=384)abort();selected.insert(ids[i]);}
    struct Job{uint64_t offset;char *dst;};std::vector<Job> jobs;
    for(int e:selected)for(int k=0;k<3;k++){uint64_t key=c.offsets[layer][k]+uint64_t(e)*EXP_BYTES;auto it=c.entries.find(key);if(it!=c.entries.end()){c.hits++;c.touch(key);}else{c.misses++;jobs.push_back({key,c.insert(key)});}}
    // The largest possible layer fits the cache, so insertion cannot evict these jobs.
    std::atomic<size_t> next{0};std::vector<std::thread> workers;
    for(int t=0;t<read_workers;t++)workers.emplace_back([&](){for(;;){size_t j=next++;if(j>=jobs.size())break;read_exact(jobs[j].dst,EXP_BYTES,jobs[j].offset);}});
    for(auto &w:workers)w.join();c.reads+=jobs.size()*EXP_BYTES;
}
extern "C" void ggml_backend_tensor_set_async(ggml_backend_t backend,ggml_tensor *tensor,const void *data,size_t offset,size_t size){
    using Fn=void(*)(ggml_backend_t,ggml_tensor*,const void*,size_t,size_t);static auto real=(Fn)dlsym(RTLD_NEXT,"ggml_backend_tensor_set_async");
    uintptr_t ptr=(uintptr_t)data;
    if(tensor->type==GGML_TYPE_Q4_K&&tensor->ne[2]==384&&getenv("MOTIF_DIRECT_LAYER")){
      constexpr size_t unit=2949120;int kind=-1,layer=-1;
      for(int l=2;l<=52;l++)if(q4_target(l))for(int k=0;k<3;k++)if(ptr>=(uintptr_t)q4_storage[l][k]&&ptr<(uintptr_t)q4_storage[l][k]+384*unit){kind=k;layer=l;}
      if(kind<0||size/unit==0||size%unit>512||offset%unit)abort();
      size_t first=(ptr-(uintptr_t)q4_storage[layer][kind])/unit,whole=size/unit,pad=size%unit;
      if((ptr-(uintptr_t)q4_storage[layer][kind])%unit)abort();
      for(size_t i=0;i<whole;i++){auto it=q4_entries.find(layer*384+first+i);if(it==q4_entries.end())abort();real(backend,tensor,it->second[kind].data(),offset+i*unit,unit+(i+1==whole?pad:0));}
      ggml_backend_synchronize(backend);return;
    }
    bool expert=tensor->type==GGML_TYPE_BF16&&tensor->ne[2]==384&&tensor->nb[2]==EXP_BYTES&&strstr(tensor->name,"_exps.weight");
    if(!enabled||!expert||ptr<model_base||ptr-model_base>=model_length){real(backend,tensor,data,offset,size);return;}
    if(size>384*EXP_BYTES||offset%EXP_BYTES)abort();auto &c=cache();uint64_t src=ptr-model_base;
    size_t whole=size/EXP_BYTES,pad=size%EXP_BYTES;if(pad>512||!whole)abort();
        Timer transfer(7);
        for(size_t i=0;i<whole;i++){
            auto it=c.entries.find(src+i*EXP_BYTES);
            if(it==c.entries.end())abort();
            size_t extra=(i+1==whole)?pad:0;
            if(extra)read_exact(it->second.data.data()+EXP_BYTES,extra,src+whole*EXP_BYTES);
            real(backend,tensor,it->second.data.data(),offset+i*EXP_BYTES,EXP_BYTES+extra);
        }
        // Keep all cached source buffers alive until their asynchronous copies finish.
        ggml_backend_synchronize(backend);
        if(!c.verified){
            std::vector<char> back(size);ggml_backend_tensor_get(tensor,back.data(),offset,size);
            for(size_t i=0;i<whole;i++){
                auto &entry=c.entries.at(src+i*EXP_BYTES);
                if(memcmp(back.data()+i*EXP_BYTES,entry.data.data(),EXP_BYTES+((i+1==whole)?pad:0)))abort();
            }
            c.verified++;
        }
        c.copies++;c.copy_bytes+=size;return;

}

extern "C" void motif_set_capacity(int gib){if(gib!=16&&gib!=32&&gib!=48)abort();motif_reset();cache().capacity=(uint64_t)gib*1024*1024*1024/EXP_BYTES;}

extern "C" void ggml_backend_tensor_set(ggml_tensor *tensor,const void *data,size_t offset,size_t size){
 using Fn=void(*)(ggml_tensor*,const void*,size_t,size_t);static auto real=(Fn)dlsym(RTLD_NEXT,"ggml_backend_tensor_set");
 uintptr_t ptr=(uintptr_t)data;const char *flag=getenv("MOTIF_LOAD_STAGING");
 if(!flag||strcmp(flag,"1")||enabled||!model_base||ptr<model_base||ptr-model_base>=model_length||ggml_backend_buffer_is_host(tensor->buffer)){real(tensor,data,offset,size);return;}
 uint64_t source_offset=ptr-model_base;
 if((tensor->type==GGML_TYPE_BF16&&tensor->ne[2]==384&&tensor->nb[2]==EXP_BYTES)||size>4ull*1024*1024*1024||size>model_length-source_offset){fprintf(stderr,"STARTUP_BOUND tensor=%s bytes=%zu src=%llu model=%zu host=%d\n",tensor->name,size,(unsigned long long)source_offset,model_length,ggml_backend_buffer_is_host(tensor->buffer));abort();}
 auto begin=TimerClock::now();startup_staging.resize(size);size_t done=0;
 while(done<size){auto got=pread(model_fd,startup_staging.data()+done,size-done,source_offset+done);if(got<0&&errno==EINTR)continue;if(got<=0){perror("startup pread");abort();}done+=got;}
 startup_read_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(TimerClock::now()-begin).count();
 begin=TimerClock::now();real(tensor,startup_staging.data(),offset,size);startup_upload_ns+=std::chrono::duration_cast<std::chrono::nanoseconds>(TimerClock::now()-begin).count();
 if(!startup_verified){std::vector<char> back(size);ggml_backend_tensor_get(tensor,back.data(),offset,size);if(memcmp(back.data(),startup_staging.data(),size)){size_t bad=0;while(bad<size&&back[bad]==startup_staging[bad])bad++;fprintf(stderr,"STARTUP_READBACK tensor=%s bytes=%zu bad_offset=%zu actual=%u expected=%u\n",tensor->name,size,bad,(unsigned char)back[bad],(unsigned char)startup_staging[bad]);abort();}startup_verified++;}
 startup_copies++;startup_bytes+=size;
}

#include "nlohmann/json.hpp"
static uint64_t direct_nodes=0;
extern "C" uint64_t motif_direct_nodes(){return direct_nodes;}
extern "C" ggml_tensor *ggml_mul_mat_id(ggml_context *ctx,ggml_tensor *a,ggml_tensor *b,ggml_tensor *ids){
 using Fn=ggml_tensor*(*)(ggml_context*,ggml_tensor*,ggml_tensor*,ggml_tensor*);static auto real=(Fn)dlsym(RTLD_NEXT,"ggml_mul_mat_id");
 const char *mode=getenv("MOTIF_DIRECT_LAYER");int kind=-1,layer=-1;
 if(mode)for(int l=2;l<=52;l++)if(q4_target(l)){std::string prefix="blk."+std::to_string(l)+".ffn_";if(a->name==prefix+"gate_exps.weight"){kind=0;layer=l;}if(a->name==prefix+"up_exps.weight"){kind=1;layer=l;}if(a->name==prefix+"down_exps.weight"){kind=2;layer=l;}}
 if(kind<0)return real(ctx,a,b,ids);
 static ggml_backend_buffer_t buffers[53][3]{};
 bool control=!strcmp(mode,"bf16");auto type=control?GGML_TYPE_BF16:GGML_TYPE_Q4_K;
 size_t unit=control?10485760:2949120,total=unit*384;
 if(!buffers[layer][kind]){
  if(control)abort();
  q4_storage[layer][kind]=mmap(nullptr,total+4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(q4_storage[layer][kind]==MAP_FAILED)abort();
  buffers[layer][kind]=ggml_backend_cpu_buffer_from_ptr(q4_storage[layer][kind],total+4096);if(!buffers[layer][kind])abort();
  ggml_backend_buffer_set_usage(buffers[layer][kind],GGML_BACKEND_BUFFER_USAGE_WEIGHTS);
  fprintf(stderr,"DIRECT_LAYER kind=%d type=%d bytes=%zu\n",kind,int(type),total);
 }
 auto replacement=ggml_new_tensor_3d(ctx,type,a->ne[0],a->ne[1],a->ne[2]);ggml_set_name(replacement,a->name);
 if(ggml_backend_tensor_alloc(buffers[layer][kind],replacement,q4_storage[layer][kind])!=GGML_STATUS_SUCCESS)abort();
 direct_nodes++;return real(ctx,replacement,b,ids);
}

static uint64_t q4_disk(const char *name){std::ifstream in(std::string("/sys/class/block/")+name+"/stat");uint64_t a,b,c;if(!(in>>a>>b>>c))abort();return c*512;}
static void q4_prefetch(int layer,const int32_t *ids,size_t count){
 constexpr size_t unit=2949120;static std::list<int> lru;static uint64_t step=0;static int fds[53]{};if(!fds[layer])fds[layer]=open(("layer"+std::to_string(layer)+".q4k").c_str(),O_RDONLY);int fd=fds[layer];
 struct stat qst;if(fd<0||fstat(fd,&qst)||qst.st_size!=3397386240LL||posix_fadvise(fd,0,0,POSIX_FADV_SEQUENTIAL))abort();size_t cap=getenv("Q4_CACHE_EXPERTS")?std::stoul(getenv("Q4_CACHE_EXPERTS")):8;
 if(cap<8||cap>8192)abort();std::set<int> selected;for(size_t i=0;i<count;i++){if(ids[i]<0||ids[i]>=384)abort();selected.insert(layer*384+ids[i]);}
 if(selected.size()>cap){fprintf(stderr,"Q4 working set exceeds cache\n");abort();}
 std::vector<std::array<std::vector<char>,3>> reusable;
 auto begin=TimerClock::now();auto nv=q4_disk("nvme0n1"),ext=q4_disk("sda");std::vector<int> missing;size_t evicted=0;
 for(int e:selected){auto it=std::find(lru.begin(),lru.end(),e);if(it!=lru.end()){lru.erase(it);lru.push_front(e);continue;}
 while(lru.size()>=cap){auto victim=lru.end();do{if(victim==lru.begin())abort();--victim;}while(selected.count(*victim));int old=*victim;lru.erase(victim);reusable.push_back(std::move(q4_entries.at(old)));q4_entries.erase(old);evicted++;}
 std::array<std::vector<char>,3> data;if(!reusable.empty()){data=std::move(reusable.back());reusable.pop_back();}else for(auto &v:data)v.resize(unit+512);q4_entries.emplace(e,std::move(data));lru.push_front(e);missing.push_back(e);
 }
 std::atomic<size_t> next{0};std::vector<std::thread> workers;
 for(size_t t=0;t<std::min<size_t>(16,missing.size()*3);t++)workers.emplace_back([&]{for(;;){size_t j=next++;if(j>=missing.size()*3)break;int e=missing[j/3],k=j%3;size_t off=(uint64_t(e%384)*3+k)*unit;if(getenv("Q4_COLD_MISS")&&posix_fadvise(fd,off,unit,POSIX_FADV_DONTNEED))abort();size_t done=0;while(done<unit){auto n=pread(fd,q4_entries.at(e)[k].data()+done,unit-done,off+done);if(n<0&&errno==EINTR)continue;if(n<=0)abort();done+=n;}}});
 for(auto &w:workers)w.join();
 fprintf(stderr,"Q4_CACHE %s\n",nlohmann::json({{"layer",layer},{"step",step++},{"selected",selected.size()},{"misses",missing.size()},{"evicted",evicted},{"resident_experts",lru.size()},{"resident_weight_bytes",lru.size()*3*unit},{"logical_bytes",missing.size()*3*unit},{"physical_nvme_bytes",q4_disk("nvme0n1")-nv},{"external_read_bytes",q4_disk("sda")-ext},{"fetch_ms",std::chrono::duration<double,std::milli>(TimerClock::now()-begin).count()}}).dump().c_str());
}
