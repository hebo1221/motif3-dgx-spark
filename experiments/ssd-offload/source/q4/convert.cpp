#include "archive_reader.h"
#include "ggml.h"
#include <thread>
#include <atomic>
#include <filesystem>
#include <sys/file.h>
constexpr size_t N=10485760,Q=2949120;
std::mutex output_mutex;
void emit(json x){std::lock_guard<std::mutex> g(output_mutex);std::cout<<x.dump()<<std::endl;}
void put(int fd,const void*p,size_t n,uint64_t off){size_t done=0;while(done<n){ssize_t z=pwrite(fd,(const char*)p+done,n-done,off+done);if(z<0&&errno==EINTR)continue;need(z>0,"write");done+=z;}}
std::string hashfile(const std::string &path){
 int fd=open(path.c_str(),O_RDONLY);need(fd>=0,"hash file");
 void*h=symbol<void*(*)()>("EVP_MD_CTX_new")();need(h,"hash ctx");need(symbol<int(*)(void*,const void*,void*)>("EVP_DigestInit_ex")(h,symbol<const void*(*)()>("EVP_sha256")(),nullptr)==1,"hash init");
 std::vector<char>b(8<<20);for(;;){ssize_t n=read(fd,b.data(),b.size());if(n<0&&errno==EINTR)continue;need(n>=0,"hash read");if(!n)break;need(symbol<int(*)(void*,const void*,size_t)>("EVP_DigestUpdate")(h,b.data(),n)==1,"hash update");}close(fd);
 unsigned char out[32];unsigned len=32;need(symbol<int(*)(void*,unsigned char*,unsigned*)>("EVP_DigestFinal_ex")(h,out,&len)==1&&len==32,"hash final");symbol<void(*)(void*)>("EVP_MD_CTX_free")(h);return hex(out);
}
#ifndef MOTIF_CONVERT_NO_MAIN
int main(int argc,char**argv){try{
 need(argc==6,"convert ARCHIVE LAYOUT OUTPUT_DIR LAYERS_CSV THREADS");
 int lock=open("/opt/motif-work/motif3-quant/campaigns/bf16-overnight-20260909-v1/worker.lock",O_CREAT|O_RDWR,0600);need(lock>=0&&!flock(lock,LOCK_EX|LOCK_NB),"worker busy");
 json layout;std::ifstream(argv[2])>>layout;ArchiveReader validated(argv[1],1);need(validated.size==layout["source_size"],"source size");
 std::string root=argv[3];std::filesystem::create_directories(root);int dfd=open(root.c_str(),O_DIRECTORY|O_RDONLY);need(dfd>=0,"output dir");
 std::vector<int>layers;std::stringstream ls(argv[4]);std::string item;while(std::getline(ls,item,',')){int l=std::stoi(item);need(l>=2&&l<=52&&std::find(layers.begin(),layers.end(),l)==layers.end(),"layer");layers.push_back(l);}
 int nt=std::stoi(argv[5]);need(nt>=1&&nt<=12,"threads");
 struct Task{int layer,kind;uint64_t offset;};std::vector<Task>tasks;std::map<int,int>fds;std::atomic<int>done[53]{};std::atomic<int>next{0};std::atomic<bool>failed{false};
 for(int l:layers){std::string name=root+"/layer"+std::to_string(l)+".q4k";need(!std::filesystem::exists(name),"published output exists");int fd=open((name+".tmp").c_str(),O_CREAT|O_EXCL|O_RDWR,0600);need(fd>=0&&!ftruncate(fd,384*3*Q),"exclusive tmp");fds[l]=fd;
 for(int k=0;k<3;k++){std::string tensor="blk."+std::to_string(l)+".ffn_"+std::vector<std::string>{"gate","up","down"}[k]+"_exps.weight";bool found=false;for(auto&s:layout["spans"])if(s["name"]==tensor){need(s["routed"]==true&&s["type"]==30&&s["length"]==384*N,"tensor span");std::vector<int>expected=k==2?std::vector<int>{1280,4096,384}:std::vector<int>{4096,1280,384};need(s["shape"]==expected,"tensor shape");tasks.push_back({l,k,s["start"]});found=true;}need(found,"missing tensor");}}
 ggml_quantize_init(GGML_TYPE_Q4_K);auto start=std::chrono::steady_clock::now();std::vector<std::thread>workers;
 for(int t=0;t<nt;t++)workers.emplace_back([&]{try{ArchiveReader reader(argv[1],2);std::vector<uint16_t>raw(N/2);std::vector<float>fp(N/2);std::vector<char>q(Q);
 for(;;){int j=next++;if(j>=int(tasks.size())||failed)break;auto task=tasks[j];int width=task.kind==2?1280:4096;
 for(int e=0;e<384;e++){if(failed)return;reader.read(raw.data(),N,task.offset+uint64_t(e)*N);for(size_t i=0;i<fp.size();i++){uint32_t bits=uint32_t(raw[i])<<16;memcpy(&fp[i],&bits,4);}need(ggml_quantize_chunk(GGML_TYPE_Q4_K,fp.data(),q.data(),0,fp.size()/width,width,nullptr)==Q,"quant size");need(ggml_validate_row_data(GGML_TYPE_Q4_K,q.data(),Q),"quant rows");put(fds.at(task.layer),q.data(),Q,(uint64_t(e)*3+task.kind)*Q);}
 emit({{"event","projection_complete"},{"layer",task.layer},{"kind",task.kind}});
 if(++done[task.layer]==3){int fd=fds.at(task.layer);need(!fsync(fd),"output fsync");std::string name=root+"/layer"+std::to_string(task.layer)+".q4k";auto sha=hashfile(name+".tmp");need(!fchmod(fd,0444),"readonly");need(!rename((name+".tmp").c_str(),name.c_str())&&!fsync(dfd),"publish");json receipt={{"event","layer_complete"},{"layer",task.layer},{"bytes",384*3*Q},{"sha256",sha},{"source_sha256","c921b7afb7fb8b5b5d90ff719e945a16988f696b8353e22bebcad2b6254362aa"},{"layout","expert-major gate/up/down"},{"type","Q4_K"},{"seconds",std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()}};int rf=open((name+".json").c_str(),O_CREAT|O_EXCL|O_WRONLY,0444);need(rf>=0,"receipt");auto s=receipt.dump(2)+"\n";writeall(rf,s.data(),s.size());need(!fsync(rf),"receipt fsync");close(rf);need(!fsync(dfd),"receipt directory");emit(receipt);}
 }}catch(const std::exception&e){failed=true;emit({{"event","worker_error"},{"error",e.what()}});}});
 for(auto&w:workers)w.join();need(!failed,"conversion failed");for(int l:layers){need(done[l]==3,"incomplete layer");close(fds[l]);}close(dfd);emit({{"event","complete"},{"layers",layers}});return 0;
 }catch(const std::exception&e){emit({{"event","fatal"},{"error",e.what()}});return 1;}}

#endif
