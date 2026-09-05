#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include "nlohmann/json.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <vector>

using json=nlohmann::json;
using clock_type=std::chrono::steady_clock;

static void require(bool value,const char * message) {
    if (!value) throw std::runtime_error(message);
}

static float random_value(uint32_t & state) {
    state=state*UINT32_C(1664525)+UINT32_C(1013904223);
    return float(state >> 8)*(1.0f/8388608.0f)-1.0f;
}

struct result {
    std::vector<float> output;
    double microseconds;
    size_t buffer_bytes;
};

static result compute(ggml_backend_t backend,int k,int m,int columns,bool invariant,
                      const std::vector<uint8_t> & weights,const std::vector<float> & input) {
    ggml_init_params params={8*ggml_tensor_overhead()+ggml_graph_overhead_custom(32,false),nullptr,true};
    std::unique_ptr<ggml_context,decltype(&ggml_free)> ctx(ggml_init(params),ggml_free);
    require(bool(ctx),"Cannot allocate tensor metadata");
    auto * a=ggml_new_tensor_2d(ctx.get(),GGML_TYPE_Q8_0,k,m);
    auto * x=ggml_new_tensor_2d(ctx.get(),GGML_TYPE_F32,k,columns);
    auto * y=ggml_mul_mat(ctx.get(),a,x);
    if (invariant) ggml_mul_mat_set_hint(y,GGML_HINT_BATCH_INVARIANT);
    ggml_set_name(y,"q8_batch_probe");
    auto * graph=ggml_new_graph_custom(ctx.get(),32,false);
    ggml_build_forward_expand(graph,y);
    require(ggml_backend_supports_op(backend,y),"Backend does not support the test operation");
    std::unique_ptr<ggml_backend_buffer,decltype(&ggml_backend_buffer_free)> buffer(
        ggml_backend_alloc_ctx_tensors(ctx.get(),backend),ggml_backend_buffer_free);
    require(bool(buffer),"Cannot allocate backend buffer");
    require(weights.size()==ggml_nbytes(a),"Quantized weight size mismatch");
    std::vector<float> repeated(size_t(k)*columns);
    for (int column=0;column<columns;++column) {
        const size_t offset=input.size()==size_t(k) ? 0 : size_t(column)*k;
        std::copy(input.begin()+offset,input.begin()+offset+k,repeated.begin()+size_t(column)*k);
    }
    ggml_backend_tensor_set(a,weights.data(),0,weights.size());
    ggml_backend_tensor_set(x,repeated.data(),0,repeated.size()*sizeof(float));
    require(ggml_backend_graph_compute(backend,graph)==GGML_STATUS_SUCCESS,"Warm-up compute failed");
    ggml_backend_synchronize(backend);
    auto start=clock_type::now();
    for (int iteration=0;iteration<25;++iteration) {
        require(ggml_backend_graph_compute(backend,graph)==GGML_STATUS_SUCCESS,"Compute failed");
    }
    ggml_backend_synchronize(backend);
    result output;
    output.microseconds=std::chrono::duration<double,std::micro>(clock_type::now()-start).count()/25;
    output.buffer_bytes=ggml_backend_buffer_get_size(buffer.get());
    output.output.resize(size_t(m)*columns);
    ggml_backend_tensor_get(y,output.output.data(),0,output.output.size()*sizeof(float));
    for (float value:output.output) require(std::isfinite(value),"Non-finite output");
    return output;
}

static std::string fingerprint(const std::vector<float> & values,size_t count) {
    uint64_t hash=UINT64_C(14695981039346656037);
    const auto * bytes=reinterpret_cast<const unsigned char *>(values.data());
    for (size_t i=0;i<count*sizeof(float);++i) hash=(hash^bytes[i])*UINT64_C(1099511628211);
    std::ostringstream out;out<<std::hex<<std::setw(16)<<std::setfill('0')<<hash;return out.str();
}

static json difference(const result & reference,const result & candidate,int m,int columns) {
    size_t different=0;
    double maximum=0,sum=0;
    for (int column=0;column<columns;++column) {
        for (int row=0;row<m;++row) {
            const float * a=&reference.output[size_t(column)*m+row];
            const float * b=&candidate.output[size_t(column)*m+row];
            different+=std::memcmp(a,b,sizeof(float))!=0;
            double delta=std::abs(double(*a)-double(*b));
            maximum=std::max(maximum,delta);sum+=delta;
        }
    }
    return {{"bitwise_equal",different==0},{"different_values",different},
            {"reference_fnv1a64",fingerprint(reference.output,size_t(m)*columns)},
            {"output_fnv1a64",fingerprint(candidate.output,size_t(m)*columns)},
            {"total_values",size_t(m)*columns},{"max_abs_difference",maximum},
            {"mean_abs_difference",sum/(m*columns)},
            {"compute_microseconds",candidate.microseconds},{"backend_buffer_bytes",candidate.buffer_bytes}};
}

int main(int argc,char ** argv) {
    try {
        require(argc==3,"Usage: q8-kernel-probe BACKEND_DIRECTORY OUTPUT.json");
        require(!std::filesystem::exists(argv[2]),"Output already exists");
        ggml_backend_load_all_from_path(argv[1]);
        std::unique_ptr<ggml_backend,decltype(&ggml_backend_free)> backend(
            ggml_backend_init_by_name("CUDA0",nullptr),ggml_backend_free);
        require(bool(backend),"CUDA0 is required for this recorded experiment");
        json output={{"status","running"},{"seed",20260905},{"fingerprint","FNV-1a-64 over float32 bytes; diagnostic, not cryptographic"},{"cases",json::array()},
                     {"backend",ggml_backend_name(backend.get())},
                     {"purpose","Synthetic Q8_0 matmul replay. No model weights, model quality, or MTP claims."},
                     {"timing_scope","25 repeated graph computes after one warm-up, excluding allocation, input transfer, and output copy"}};
        for (auto dimensions:std::vector<std::pair<int,int>>{{2048,4096},{4096,4096},{4096,16384}}) {
            int k=dimensions.first,m=dimensions.second;
            uint32_t state=20260905;
            std::vector<float> dense(size_t(k)*m),input(size_t(k)*8);
            for (float & value:dense) value=random_value(state);
            for (float & value:input) value=random_value(state);
            std::vector<uint8_t> weights(ggml_row_size(GGML_TYPE_Q8_0,k)*m);
            auto bytes=ggml_quantize_chunk(GGML_TYPE_Q8_0,dense.data(),weights.data(),0,m,k,nullptr);
            require(bytes==weights.size(),"Quantizer returned an unexpected size");
            dense.clear();dense.shrink_to_fit();
            auto reference=compute(backend.get(),k,m,1,false,weights,input);
            for (int column=1;column<8;++column) {
                std::vector<float> x(input.begin()+size_t(column)*k,input.begin()+size_t(column+1)*k);
                auto single=compute(backend.get(),k,m,1,false,weights,x);
                reference.output.insert(reference.output.end(),single.output.begin(),single.output.end());
            }
            json test={{"k",k},{"m",m},{"weight_bytes",weights.size()},
                       {"single_column_microseconds",reference.microseconds},{"widths",json::array()}};
            for (int columns:{2,4,8}) {
                auto ordinary=compute(backend.get(),k,m,columns,false,weights,input);
                auto invariant=compute(backend.get(),k,m,columns,true,weights,input);
                auto row=json({{"width",columns},{"ordinary",difference(reference,ordinary,m,columns)},
                               {"invariant_hint",difference(reference,invariant,m,columns)}});
                test["widths"].push_back(row);
                std::cout << json({{"k",k},{"m",m},{"width",columns},
                    {"ordinary_equal",row["ordinary"]["bitwise_equal"]},
                    {"hint_equal",row["invariant_hint"]["bitwise_equal"]}}).dump() << std::endl;
            }
            auto restored=compute(backend.get(),k,m,1,false,weights,input);
            test["repeat_control"]=difference(reference,restored,m,1);
            require(test["repeat_control"]["bitwise_equal"],"Single-column repeat control differs");
            output["cases"].push_back(test);
        }
        output["loaded_library_mappings"]=json::array();
        std::ifstream maps("/proc/self/maps");std::string line;
        while (std::getline(maps,line)) {
            if (line.find("libggml")!=std::string::npos) output["loaded_library_mappings"].push_back(line);
        }
        output["status"]="completed";
        std::ofstream file(argv[2]);file << output.dump(2) << '\n';
        require(bool(file),"Cannot finish result file");
        ggml_quantize_free();
        return 0;
    } catch (const std::exception & error) {
        std::cerr << error.what() << '\n';return 1;
    }
}
