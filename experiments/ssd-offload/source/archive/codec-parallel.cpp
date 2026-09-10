#include <zstd.h>
#include <future>
#include <deque>
#include <dlfcn.h>
#include <vector>
#include <array>
#include <string>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include "nlohmann/json.hpp"
using json=nlohmann::json;
void need(bool x,const char *m){if(!x)throw std::runtime_error(m);}
void readat(int fd,void *p,size_t n,uint64_t off){size_t done=0;while(done<n){auto z=pread(fd,(char*)p+done,n-done,off+done);if(z<0&&errno==EINTR)continue;need(z>0,"short read");done+=z;}}
void writeall(int fd,const void *p,size_t n){size_t done=0;while(done<n){auto z=write(fd,(const char*)p+done,n-done);if(z<0&&errno==EINTR)continue;need(z>0,"short write");done+=z;}}
template<class T>T symbol(const char *name){static void *lib=dlopen("libcrypto.so.3",RTLD_NOW|RTLD_LOCAL);need(lib,"crypto library");auto fn=(T)dlsym(lib,name);need(fn,"crypto symbol");return fn;}
std::array<unsigned char,32> digest(const std::vector<unsigned char>&v){std::array<unsigned char,32> h;need(symbol<unsigned char*(*)(const unsigned char*,size_t,unsigned char*)>("SHA256")(v.data(),v.size(),h.data()),"SHA256");return h;}
std::string hex(const unsigned char *h){char out[65];for(int i=0;i<32;i++)snprintf(out+i*2,3,"%02x",h[i]);return out;}
constexpr char magic[8]={'M','B','F','1','6','Z','1',0};
constexpr uint64_t limit=512ull<<20;
std::vector<unsigned char> decode(const std::string&path,json *receipt=nullptr){
 int fd=open(path.c_str(),O_RDONLY);struct stat st;need(fd>=0&&!fstat(fd,&st),"open frame");need(st.st_size>=48&&uint64_t(st.st_size)<=ZSTD_compressBound(limit)+48,"frame size");
 std::vector<unsigned char> frame(st.st_size);readat(fd,frame.data(),frame.size(),0);close(fd);
 need(!memcmp(frame.data(),magic,8),"magic");uint64_t n;memcpy(&n,frame.data()+8,8);need(n>0&&n<=limit,"raw bound");
 std::vector<unsigned char> shuffled(n),raw(n);auto z=ZSTD_decompress(shuffled.data(),n,frame.data()+48,frame.size()-48);need(!ZSTD_isError(z)&&z==n,"decompress");size_t half=(n+1)/2;
 for(size_t i=0;i<n/2;i++){raw[2*i]=shuffled[i];raw[2*i+1]=shuffled[half+i];}if(n%2)raw[n-1]=shuffled[half-1];
 auto h=digest(raw);need(!memcmp(h.data(),frame.data()+16,32),"raw SHA256 mismatch");
 if(receipt){auto fh=digest(frame);*receipt={{"raw_bytes",n},{"raw_sha256",hex(h.data())},{"frame_bytes",frame.size()},{"frame_sha256",hex(fh.data())}};}
 return raw;
}
int main(int argc,char **argv){try{
 need(argc>=3,"usage");std::string cmd=argv[1];
 if(cmd=="encode"){
  need(argc==6,"encode source offset length output");uint64_t off=std::stoull(argv[3]),n=std::stoull(argv[4]);need(n>0&&n<=limit,"length");
  int fd=open(argv[2],O_RDONLY);need(fd>=0,"source");std::vector<unsigned char> raw(n),shuffled(n);readat(fd,raw.data(),n,off);close(fd);
  auto h=digest(raw);size_t half=(n+1)/2;for(size_t i=0;i<n/2;i++){shuffled[i]=raw[2*i];shuffled[half+i]=raw[2*i+1];}if(n%2)shuffled[half-1]=raw[n-1];
  std::vector<unsigned char> frame(ZSTD_compressBound(n)+48);memcpy(frame.data(),magic,8);memcpy(frame.data()+8,&n,8);memcpy(frame.data()+16,h.data(),32);
  auto ctx=ZSTD_createCCtx();need(ctx,"zstd ctx");
  need(!ZSTD_isError(ZSTD_CCtx_setParameter(ctx,ZSTD_c_compressionLevel,3)),"level");need(!ZSTD_isError(ZSTD_CCtx_setParameter(ctx,ZSTD_c_nbWorkers,8)),"workers");need(!ZSTD_isError(ZSTD_CCtx_setParameter(ctx,ZSTD_c_checksumFlag,1)),"checksum");
  auto z=ZSTD_compress2(ctx,frame.data()+48,frame.size()-48,shuffled.data(),n);ZSTD_freeCCtx(ctx);need(!ZSTD_isError(z),"compress");frame.resize(z+48);
  fd=open(argv[5],O_WRONLY|O_CREAT|O_EXCL,0600);need(fd>=0,"exclusive output");writeall(fd,frame.data(),frame.size());need(!fsync(fd)&&!close(fd),"frame fsync");
  std::vector<unsigned char>().swap(frame);std::vector<unsigned char>().swap(shuffled);
  json receipt;auto restored=decode(argv[5],&receipt);need(restored==raw,"readback parity");receipt["offset"]=off;std::cout<<receipt.dump()<<std::endl;
 }else if(cmd=="check"){json receipt;decode(argv[2],&receipt);std::cout<<receipt.dump()<<std::endl;
 }else if(cmd=="decode"){need(argc==4,"decode frame output");auto raw=decode(argv[2]);int fd=std::string(argv[3])=="-"?STDOUT_FILENO:open(argv[3],O_WRONLY|O_CREAT|O_EXCL,0600);need(fd>=0,"decode output");writeall(fd,raw.data(),raw.size());if(fd!=STDOUT_FILENO){need(!fsync(fd),"decode fsync");close(fd);}
 }else if(cmd=="hash"){
  std::ifstream in(argv[2]);need(bool(in),"frame list");void *h=symbol<void*(*)()>("EVP_MD_CTX_new")();need(h,"hash context");need(symbol<int(*)(void*,const void*,void*)>("EVP_DigestInit_ex")(h,symbol<const void*(*)()>("EVP_sha256")(),nullptr)==1,"hash init");uint64_t bytes=0;std::string path;std::deque<std::future<std::vector<unsigned char>>> pending;
 auto enqueue=[&](){if(!std::getline(in,path))return false;pending.emplace_back(std::async(std::launch::async,[file=path](){return decode(file);}));return true;};
 for(int i=0;i<8;i++)if(!enqueue())break;
 size_t count=0;
 while(!pending.empty()){
  auto raw=pending.front().get();pending.pop_front();
  need(symbol<int(*)(void*,const void*,size_t)>("EVP_DigestUpdate")(h,raw.data(),raw.size())==1,"hash update");bytes+=raw.size();
  std::vector<unsigned char>().swap(raw);enqueue();
  if(++count%32==0)std::cerr<<json({{"event","hash_progress"},{"frames",count},{"raw_bytes",bytes}}).dump()<<std::endl;
 }unsigned char out[32];unsigned int len=32;need(symbol<int(*)(void*,unsigned char*,unsigned int*)>("EVP_DigestFinal_ex")(h,out,&len)==1&&len==32,"hash final");symbol<void(*)(void*)>("EVP_MD_CTX_free")(h);std::cout<<json({{"raw_bytes",bytes},{"raw_sha256",hex(out)}}).dump()<<std::endl;
 }else need(false,"unknown command");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
