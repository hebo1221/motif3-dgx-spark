#include "llama.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "nlohmann/json.hpp"
#include <dlfcn.h>
#include <fstream>
#include <chrono>
#include <cmath>
#include <cstring>
#include <iostream>
#include <vector>
#include <string>
#include <stdexcept>
using json=nlohmann::json;using Clock=std::chrono::steady_clock;
static double elapsed(Clock::time_point t){return std::chrono::duration<double>(Clock::now()-t).count();}
static void require(bool b,const char *s){if(!b)throw std::runtime_error(s);}
static void emit(const json &j){std::cout<<j.dump(-1,' ',false,json::error_handler_t::replace)<<std::endl;}
struct State{void(*prefetch)(int,const int32_t*,size_t)=nullptr;size_t routes=0;};
static bool callback(ggml_tensor*t,bool ask,void*opaque){
 State&s=*(State*)opaque;std::string n=t->name,p="ffn_moe_topk-";
 bool route=n.rfind(p,0)==0&&n.size()>p.size()&&n.find_first_not_of("0123456789",p.size())==std::string::npos;
 if(ask)return route;if(!route)return true;
 require(t->type==GGML_TYPE_I32&&t->ne[0]==8&&t->ne[1]<=16,"Unexpected routing shape");
 std::vector<char>b(ggml_nbytes(t));ggml_backend_tensor_get(t,b.data(),0,b.size());std::vector<int32_t>ids;
 for(int64_t j=0;j<t->ne[1];j++)for(int i=0;i<8;i++){int32_t id;memcpy(&id,b.data()+j*t->nb[1]+i*t->nb[0],4);ids.push_back(id);}
 s.prefetch(std::stoi(n.substr(p.size())),ids.data(),ids.size());s.routes++;return true;
}
int main(int argc,char**argv){try{
 require(argc==3,"usage: probe MODEL BACKEND_DIR");State s;
 auto enable=(void(*)(int))dlsym(RTLD_DEFAULT,"motif_enable");s.prefetch=(void(*)(int,const int32_t*,size_t))dlsym(RTLD_DEFAULT,"motif_prefetch");
 auto capacity=(void(*)(int))dlsym(RTLD_DEFAULT,"motif_set_capacity");auto fast=(void(*)(int))dlsym(RTLD_DEFAULT,"motif_fast");auto workers=(void(*)(int))dlsym(RTLD_DEFAULT,"motif_workers");auto dynamic=(void(*)(int))dlsym(RTLD_DEFAULT,"motif_dynamic");auto disk=(void(*)(uint64_t*))dlsym(RTLD_DEFAULT,"motif_disk_stats");auto overlay=(void(*)(uint64_t*))dlsym(RTLD_DEFAULT,"motif_overlay_stats");
 require(enable&&s.prefetch&&capacity&&fast&&workers&&dynamic&&disk&&overlay,"Loader exports unavailable");
 ggml_backend_load_all_from_path(argv[2]);llama_model_tensor_buft_override ov[]={{"\\.ffn_(gate|up|down)_exps\\.weight",ggml_backend_cpu_buffer_type()},{nullptr,nullptr}};
 auto mp=llama_model_default_params();mp.n_gpu_layers=99;mp.load_mode=LLAMA_LOAD_MODE_MMAP;mp.tensor_buft_overrides=ov;mp.use_extra_bufts=false;mp.load_mtp=false;
 auto load_start=Clock::now();auto*model=llama_model_load_from_file(argv[1],mp);require(model,"Model load failed");double load_s=elapsed(load_start);
 auto cp=llama_context_default_params();cp.n_ctx=2048;cp.n_batch=16;cp.n_ubatch=16;cp.n_seq_max=1;cp.n_threads=12;cp.n_threads_batch=12;cp.type_k=GGML_TYPE_F16;cp.type_v=GGML_TYPE_F16;cp.flash_attn_type=LLAMA_FLASH_ATTN_TYPE_DISABLED;cp.offload_kqv=true;cp.op_offload=true;cp.kv_unified=true;cp.cb_eval=callback;cp.cb_eval_user_data=&s;
 auto*ctx=llama_init_from_model(model,cp);require(ctx,"Context creation failed");const auto*vocab=llama_model_get_vocab(model);
 auto nodes=(uint64_t(*)())dlsym(RTLD_DEFAULT,"motif_direct_nodes");require(nodes&&nodes()>=153&&nodes()%153==0,"All Q4 projections must be replaced");emit({{"event","q4_graph_verified"},{"direct_nodes",nodes()},{"initialization_seconds",elapsed(load_start)}});dynamic(0);enable(1);fast(1);capacity(16);workers(16);emit({{"event","ready"},{"load_seconds",load_s},{"context_tokens",2048}});
 std::string line;while(std::getline(std::cin,line)){
  json req;std::string id,prompt;int limit;std::vector<llama_token>tokens(1025);
  try{require(line.size()<=131072,"Request too large");req=json::parse(line);id=req.at("id").get<std::string>();prompt=req.at("prompt").get<std::string>();require(id.size()<=128&&prompt.size()<=65536,"Input too large");require(req.at("max_tokens").is_number_integer(),"max_tokens must be integer");auto lim=req.at("max_tokens").get<int64_t>();require(lim>=1&&lim<=1024,"max_tokens must be 1..1024");limit=int(lim);
   int n=llama_tokenize(vocab,prompt.data(),prompt.size(),tokens.data(),tokens.size(),req.value("add_bos",false),true);require(n>0&&n<=1024,"Rendered question exceeds 1024 tokens");tokens.resize(n);require(n+limit<=2048,"Context budget exceeded");
  }catch(const std::exception&e){emit({{"event","request_error"},{"id",id},{"error",e.what()}});continue;}
  llama_memory_clear(llama_get_memory(ctx),true);s.routes=0;int pos=0,batches=0;double prefill_s=0,decode_s=0;auto start=Clock::now();uint64_t db[3],da[3],ob[6],oa[6];disk(db);overlay(ob);
  auto decode=[&](const std::vector<llama_token>&input){auto batch=llama_batch_init(input.size(),0,1);batch.n_tokens=input.size();for(size_t j=0;j<input.size();j++){batch.token[j]=input[j];batch.pos[j]=pos++;batch.n_seq_id[j]=1;batch.seq_id[j][0]=0;batch.logits[j]=(j+1==input.size());}auto t=Clock::now();int rc=llama_decode(ctx,batch);llama_batch_free(batch);require(rc==0,"llama_decode failed");batches++;return elapsed(t);};
  for(size_t i=0;i<tokens.size();i+=16){std::vector<llama_token>part(tokens.begin()+i,tokens.begin()+std::min(i+16,tokens.size()));prefill_s+=decode(part);emit({{"event","prefill"},{"id",id},{"prompt_tokens_done",pos},{"prompt_tokens",tokens.size()},{"seconds",prefill_s}});}
  std::vector<llama_token>generated;std::string text,finish="length";
  for(int step=0;step<limit;step++){
   auto*logits=llama_get_logits_ith(ctx,-1);require(logits,"Missing logits");int best=0,nv=llama_vocab_n_tokens(vocab);{std::ofstream f("logits-"+id+"-"+std::to_string(step)+".bin",std::ios::binary);f.write((char*)logits,nv*sizeof(float));require(bool(f),"logits write");}for(int i=0;i<nv;i++){require(std::isfinite(logits[i]),"Nonfinite logits");if(logits[i]>logits[best])best=i;}generated.push_back(best);
   if(llama_vocab_is_eog(vocab,best)){finish="stop";emit({{"event","token"},{"id",id},{"token_id",best},{"generated_tokens",generated.size()},{"text",text},{"eog",true}});break;}
   std::vector<char>piece(256);int n=llama_token_to_piece(vocab,best,piece.data(),piece.size(),0,true);if(n<0){piece.resize(-n);n=llama_token_to_piece(vocab,best,piece.data(),piece.size(),0,true);}require(n>=0,"Token decode failed");text.append(piece.data(),n);
   emit({{"event","token"},{"id",id},{"token_id",best},{"generated_tokens",generated.size()},{"text",text},{"elapsed_seconds",elapsed(start)}});
   if(step+1<limit)decode_s+=decode({best});
  }
  require(s.routes==51*size_t(batches),"Routing callbacks missing");disk(da);overlay(oa);require(oa[1]==ob[1],"Unexpected cache write");
  emit({{"event","request_complete"},{"id",id},{"text",text},{"generated_ids",generated},{"generated_tokens",generated.size()},{"prompt_tokens",tokens.size()},{"finish_reason",finish},{"request_seconds",elapsed(start)},{"prefill_seconds",prefill_s},{"decode_seconds",decode_s},{"source_read_bytes",da[2]-db[2]},{"nvme_read_bytes",da[1]-db[1]},{"overlay_writes",oa[1]-ob[1]}});
 }
 llama_free(ctx);llama_model_free(model);emit({{"event","worker_complete"},{"resources_freed",true}});return 0;
}catch(const std::exception&e){emit({{"event","fatal"},{"error",e.what()}});return 1;}}
