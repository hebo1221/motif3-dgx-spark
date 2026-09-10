#define MOTIF_CONVERT_NO_MAIN
#include "convert.cpp"
#undef MOTIF_CONVERT_NO_MAIN
std::string hash_range_file(const std::string &path,uint64_t offset,uint64_t length){
 int fd=open(path.c_str(),O_RDONLY);need(fd>=0,"hash file");
 void*h=symbol<void*(*)()>("EVP_MD_CTX_new")();need(h,"hash ctx");need(symbol<int(*)(void*,const void*,void*)>("EVP_DigestInit_ex")(h,symbol<const void*(*)()>("EVP_sha256")(),nullptr)==1,"hash init");
 need(lseek(fd,offset,SEEK_SET)==off_t(offset),"range seek");std::vector<char>b(8<<20);while(length){ssize_t n=read(fd,b.data(),std::min<uint64_t>(b.size(),length));if(n<0&&errno==EINTR)continue;need(n>=0,"hash read");need(n>0,"short range");length-=n;need(symbol<int(*)(void*,const void*,size_t)>("EVP_DigestUpdate")(h,b.data(),n)==1,"hash update");}close(fd);
 unsigned char out[32];unsigned len=32;need(symbol<int(*)(void*,unsigned char*,unsigned*)>("EVP_DigestFinal_ex")(h,out,&len)==1&&len==32,"hash final");symbol<void(*)(void*)>("EVP_MD_CTX_free")(h);return hex(out);
}
int main(int argc,char**argv){try{
 need(argc==4,"shell ARCHIVE LAYOUT OUTPUT");
 int lock=open("/opt/motif-work/motif3-quant/campaigns/bf16-overnight-20260909-v1/worker.lock",O_CREAT|O_RDWR,0600);need(lock>=0&&!flock(lock,LOCK_EX|LOCK_NB),"worker busy");
 ArchiveReader reader(argv[1],2);json layout;std::ifstream(argv[2])>>layout;need(reader.size==layout["source_size"],"source size");
 std::string out=argv[3];need(!std::filesystem::exists(out),"output exists");int fd=open((out+".tmp").c_str(),O_CREAT|O_EXCL|O_RDWR,0600);need(fd>=0&&!ftruncate(fd,reader.size),"exclusive sparse file");
 json ranges=json::array();ranges.push_back({{"name","GGUF_HEADER"},{"start",0},{"length",layout["data_offset"]}});for(auto&s:layout["spans"])if(!s["routed"].get<bool>())ranges.push_back(s);
 std::vector<unsigned char>b(8<<20),back(b.size());uint64_t total=0;
 for(auto&r:ranges){uint64_t off=r["start"],n=r["length"];for(uint64_t done=0;done<n;){size_t z=std::min<uint64_t>(b.size(),n-done);reader.read(b.data(),z,off+done);put(fd,b.data(),z,off+done);readat(fd,back.data(),z,off+done);need(!memcmp(b.data(),back.data(),z),"ordinary readback");done+=z;}r["sha256"]=hash_range_file(out+".tmp",off,n);total+=n;}
 need(!fsync(fd),"shell fsync");struct stat st;need(!fstat(fd,&st),"shell stat");need(!fchmod(fd,0444),"shell readonly");close(fd);need(!rename((out+".tmp").c_str(),out.c_str()),"shell publish");
 json receipt={{"format","SPARSE_Q4_SHELL_NOT_STANDALONE"},{"logical_bytes",reader.size},{"ordinary_bytes",total},{"allocated_bytes",uint64_t(st.st_blocks)*512},{"routed_tensors_are_holes",true},{"requires_q4_layers",51},{"ordinary_readback_byte_exact",true},{"source_sha256","c921b7afb7fb8b5b5d90ff719e945a16988f696b8353e22bebcad2b6254362aa"},{"ranges",ranges}};
 int rf=open((out+".json").c_str(),O_CREAT|O_EXCL|O_WRONLY,0444);need(rf>=0,"shell receipt");auto text=receipt.dump(2)+"\n";writeall(rf,text.data(),text.size());need(!fsync(rf),"receipt fsync");close(rf);int dir=open(std::filesystem::path(out).parent_path().c_str(),O_DIRECTORY|O_RDONLY);need(dir>=0&&!fsync(dir),"directory fsync");close(dir);emit({{"event","shell_complete"},{"ordinary_bytes",total},{"allocated_bytes",uint64_t(st.st_blocks)*512}});return 0;
}catch(const std::exception&e){emit({{"event","fatal"},{"error",e.what()}});return 1;}}
