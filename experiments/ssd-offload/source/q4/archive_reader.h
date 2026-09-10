#pragma once
#define main codec_internal_main
#include "codec-fast.cpp"
#undef main
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <algorithm>
// Only complete archives are accepted. The writer cannot run after completion.
class ArchiveReader {
 struct Entry { uint64_t offset,size;std::string file,raw_hash,frame_hash; };
 std::string root;std::vector<Entry> entries;std::mutex mutex;
 std::list<uint64_t> age;
 std::map<uint64_t,std::shared_ptr<std::vector<unsigned char>>> cache;
 size_t capacity;
public:
 uint64_t size=0;
 ArchiveReader(std::string path,size_t cap=6):root(std::move(path)),capacity(cap){
  need(cap>0&&cap<=16,"archive cache capacity");json s;std::ifstream(root+"/state.json")>>s;
  need(s["phase"]=="complete","archive not complete");size=s["source_size"];
  need(s["verification"]["raw_bytes"]==size&&s["verification"]["raw_sha256"]==s["expected_sha256"],"archive verification receipt");
  for(auto &e:s["entries"])entries.push_back({e["offset"],e["raw_bytes"],e["file"],e["raw_sha256"],e["frame_sha256"]});
  std::sort(entries.begin(),entries.end(),[](auto&a,auto&b){return a.offset<b.offset;});
  uint64_t end=0;for(auto &e:entries){need(e.offset==end,"archive gap");end+=e.size;}need(end==size,"archive coverage");
 }
 void read(void *destination,size_t n,uint64_t offset){
  std::lock_guard<std::mutex> guard(mutex);need(offset<=size&&n<=size-offset,"archive range");auto out=(unsigned char*)destination;
  while(n){
   auto it=std::upper_bound(entries.begin(),entries.end(),offset,[](uint64_t off,const Entry&e){return off<e.offset;});need(it!=entries.begin(),"range entry");--it;
   auto hit=cache.find(it->offset);
   if(hit==cache.end()){
    while(cache.size()>=capacity){cache.erase(age.back());age.pop_back();}
    json receipt;auto raw=decode(root+"/"+it->file,&receipt);
    need(receipt["raw_sha256"]==it->raw_hash&&receipt["frame_sha256"]==it->frame_hash&&raw.size()==it->size,"archive entry receipt mismatch");
    hit=cache.emplace(it->offset,std::make_shared<std::vector<unsigned char>>(std::move(raw))).first;
   }else age.remove(it->offset);
   age.push_front(it->offset);size_t within=offset-it->offset,part=std::min<uint64_t>(n,it->size-within);
   need(part>0,"empty archive part");memcpy(out,hit->second->data()+within,part);out+=part;offset+=part;n-=part;
  }
 }
};
