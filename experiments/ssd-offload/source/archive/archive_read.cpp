#include "archive_reader.h"
int main(int argc,char**argv){try{
 need(argc==6,"usage: archive_read ARCHIVE OFFSET LENGTH OUTPUT CACHE_FRAMES");ArchiveReader reader(argv[1],std::stoul(argv[5]));uint64_t offset=std::stoull(argv[2]),n=std::stoull(argv[3]);
 need(n<=512ull<<20,"range output bound");std::vector<unsigned char> out(n);reader.read(out.data(),n,offset);
 int fd=open(argv[4],O_WRONLY|O_CREAT|O_EXCL,0600);need(fd>=0,"range output exists");writeall(fd,out.data(),out.size());need(!fsync(fd),"range output fsync");close(fd);return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
