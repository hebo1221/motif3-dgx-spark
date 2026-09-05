#include "llama.h"
#include "ggml-backend.h"
#include "nlohmann/json.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <vector>

using json = nlohmann::json;
using clock_type = std::chrono::steady_clock;
using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
using context_ptr = std::unique_ptr<llama_context, decltype(&llama_free)>;

static double elapsed(clock_type::time_point start) {
    return std::chrono::duration<double>(clock_type::now() - start).count();
}

static void require(bool value, const char * message) {
    if (!value) throw std::runtime_error(message);
}

static std::string fingerprint(const float * values, size_t count) {
    uint64_t hash = UINT64_C(14695981039346656037);
    const auto * bytes = reinterpret_cast<const unsigned char *>(values);
    for (size_t i = 0; i < count * sizeof(float); ++i) {
        hash = (hash ^ bytes[i]) * UINT64_C(1099511628211);
    }
    std::ostringstream out;
    out << std::hex << std::setw(16) << std::setfill('0') << hash;
    return out.str();
}

static int argmax(const float * values, int count) {
    require(count > 1, "Vocabulary is too small");
    int best = 0;
    for (int i = 0; i < count; ++i) {
        require(std::isfinite(values[i]), "Non-finite logit");
        if (values[i] > values[best]) best = i;
    }
    return best;
}

static json describe_row(const float * values, int count) {
    int best = argmax(values, count);
    int second = best == 0 ? 1 : 0;
    for (int i = 0; i < count; ++i) {
        if (i != best && values[i] > values[second]) second = i;
    }
    return {{"argmax", best}, {"runner_up", second}, {"margin", double(values[best]) - values[second]},
            {"fnv1a64", fingerprint(values, count)}};
}

static json compare_row(const float * before, const float * after, int count) {
    double sum = 0, maximum = 0;
    size_t different = 0;
    for (int i = 0; i < count; ++i) {
        require(std::isfinite(before[i]) && std::isfinite(after[i]), "Non-finite comparison");
        double difference = std::abs(double(before[i]) - double(after[i]));
        sum += difference;
        maximum = std::max(maximum, difference);
        if (std::memcmp(before + i, after + i, sizeof(float)) != 0) ++different;
    }
    return {{"bitwise_equal", different == 0}, {"different_values", different},
            {"max_abs_difference", maximum}, {"mean_abs_difference", sum / count},
            {"argmax_equal", argmax(before, count) == argmax(after, count)}};
}

static void decode(llama_context * ctx, const std::vector<llama_token> & tokens,
                   int begin, int count, int position, bool all_logits) {
    require(count > 0 && begin >= 0 && size_t(begin + count) <= tokens.size(), "Invalid batch bounds");
    llama_batch batch = llama_batch_init(count, 0, 1);
    batch.n_tokens = count;
    for (int i = 0; i < count; ++i) {
        batch.token[i] = tokens[begin + i];
        batch.pos[i] = position + i;
        batch.n_seq_id[i] = 1;
        batch.seq_id[i][0] = 0;
        batch.logits[i] = all_logits || i == count - 1;
    }
    int result = llama_decode(ctx, batch);
    llama_batch_free(batch);
    require(result == 0, "llama_decode failed");
}

static std::vector<llama_token> tokenize(const llama_vocab * vocab, const std::string & prompt) {
    int count = -llama_tokenize(vocab, prompt.data(), prompt.size(), nullptr, 0, true, true);
    require(count > 0 && count <= 1536, "Prompt must contain 1 to 1536 tokens");
    std::vector<llama_token> tokens(count);
    int written = llama_tokenize(vocab, prompt.data(), prompt.size(), tokens.data(), count, true, true);
    require(written == count, "Tokenizer length changed");
    return tokens;
}

static void prefill(llama_context * ctx, const std::vector<llama_token> & tokens) {
    for (int begin = 0; begin < int(tokens.size()); begin += 256) {
        int count = std::min(256, int(tokens.size()) - begin);
        decode(ctx, tokens, begin, count, begin, false);
    }
}

static context_ptr make_context(llama_model * model, bool flash) {
    auto params = llama_context_default_params();
    params.n_ctx = 2048;
    params.n_batch = 256;
    params.n_ubatch = 256;
    params.n_seq_max = 1;
    params.n_threads = 20;
    params.n_threads_batch = 20;
    params.type_k = GGML_TYPE_F16;
    params.type_v = GGML_TYPE_F16;
    params.flash_attn_type = flash ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_DISABLED;
    params.no_perf = false;
    context_ptr ctx(llama_init_from_model(model, params), llama_free);
    require(bool(ctx), "Cannot initialize context");
    return ctx;
}

static std::vector<llama_token> generate_trace(llama_model * model, const std::vector<llama_token> & prompt,
                                             int count, bool flash) {
    auto ctx = make_context(model, flash);
    const auto * vocab = llama_model_get_vocab(model);
    int n_vocab = llama_vocab_n_tokens(vocab);
    prefill(ctx.get(), prompt);
    std::vector<llama_token> trace;
    for (int i = 0; i < count; ++i) {
        const float * logits = llama_get_logits_ith(ctx.get(), -1);
        require(logits != nullptr, "Missing generation logits");
        llama_token token = argmax(logits, n_vocab);
        if (llama_vocab_is_eog(vocab, token)) break;
        trace.push_back(token);
        decode(ctx.get(), trace, i, 1, prompt.size() + i, true);
    }
    require(!trace.empty(), "Trace stopped before a continuation token");
    return trace;
}

struct evaluation {
    std::vector<std::vector<float>> logits;
    json receipt;
};

static evaluation evaluate(llama_model * model, const std::vector<llama_token> & prompt,
                           const std::vector<llama_token> & trace, int width, bool flash) {
    require(width >= 1 && width <= 16, "Width must be between 1 and 16");
    auto start = clock_type::now();
    auto ctx = make_context(model, flash);
    int n_vocab = llama_vocab_n_tokens(llama_model_get_vocab(model));
    prefill(ctx.get(), prompt);
    evaluation result;
    result.receipt = {{"width", width}, {"rows", json::array()}, {"prefill_seconds", elapsed(start)}};
    auto decode_start = clock_type::now();
    for (int begin = 0; begin < int(trace.size()); begin += width) {
        int count = std::min(width, int(trace.size()) - begin);
        decode(ctx.get(), trace, begin, count, prompt.size() + begin, true);
        for (int row = 0; row < count; ++row) {
            const float * logits = llama_get_logits_ith(ctx.get(), row);
            require(logits != nullptr, "Missing evaluation logits");
            result.logits.emplace_back(logits, logits + n_vocab);
            json item = describe_row(logits, n_vocab);
            item["position"] = prompt.size() + begin + row;
            item["input_token"] = trace[begin + row];
            result.receipt["rows"].push_back(item);
        }
    }
    result.receipt["decode_and_copy_seconds"] = elapsed(decode_start);
    result.receipt["total_seconds"] = elapsed(start);
    return result;
}

static json compare(const evaluation & reference, const evaluation & candidate) {
    require(reference.logits.size() == candidate.logits.size(), "Row count mismatch");
    json rows = json::array();
    int different_rows = 0, different_argmax = 0;
    for (size_t i = 0; i < reference.logits.size(); ++i) {
        require(reference.logits[i].size() == candidate.logits[i].size(), "Vocabulary mismatch");
        auto row = compare_row(reference.logits[i].data(), candidate.logits[i].data(), reference.logits[i].size());
        row["row"] = i;
        different_rows += !row["bitwise_equal"].get<bool>();
        different_argmax += !row["argmax_equal"].get<bool>();
        rows.push_back(row);
    }
    return {{"different_logit_rows", different_rows}, {"different_argmax_rows", different_argmax},
            {"row_count", rows.size()}, {"rows", rows}};
}

static void self_test() {
    float a[] = {1, 2, 3}, b[] = {1, 2, 3}, c[] = {1, 4, 3}, d[] = {1, 2, 3.0001f};
    require(compare_row(a, b, 3)["bitwise_equal"], "Equal rows failed");
    require(!compare_row(a, c, 3)["argmax_equal"].get<bool>(), "Changed argmax missed");
    require(!compare_row(a, d, 3)["bitwise_equal"].get<bool>(), "Small change missed");
    require(compare_row(a, d, 3)["argmax_equal"], "Stable argmax failed");
    float tie[] = {3, 3, 2};
    require(argmax(tie, 3) == 0, "Tie handling differs from greedy scan");
    float bad[] = {1, INFINITY, 2};
    bool rejected = false;
    try { (void) compare_row(a, bad, 3); } catch (...) { rejected = true; }
    require(rejected, "Non-finite logits accepted");
    std::cout << "{\"status\":\"pass\",\"checks\":6}\n";
}

int main(int argc, char ** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") { self_test(); return 0; }
        require(argc == 5, "Usage: batch-probe MODEL INPUT.json OUTPUT.json BACKEND_DIRECTORY");
        require(!std::filesystem::exists(argv[3]), "Output already exists");
        std::ifstream input(argv[2]);
        json config = json::parse(input);
        require(config["cases"].is_array() && config["cases"].size() <= 8, "One to eight cases are supported");
        require(!config["cases"].empty(), "No cases supplied");
        ggml_backend_load_all_from_path(argv[4]);
        auto params = llama_model_default_params();
        params.n_gpu_layers = -1;
        model_ptr model(llama_model_load_from_file(argv[1], params), llama_model_free);
        require(bool(model), "Cannot load model");
        const auto * vocab = llama_model_get_vocab(model.get());
        int n_vocab = llama_vocab_n_tokens(vocab);
        bool flash = config.value("flash_attention", true);
        json output = {{"status", "running"}, {"schema_version", 1}, {"cases", json::array()},
                       {"model_path", argv[1]}, {"vocab_size", n_vocab}, {"flash_attention", flash},
                       {"fingerprint", "FNV-1a-64 over native float32 bytes; diagnostic, not a cryptographic hash"},
                       {"mode", "fixed continuation replay; this is not speculative sampling or an accuracy benchmark"}};
        std::ifstream maps("/proc/self/maps");
        std::string line;
        output["loaded_library_mappings"] = json::array();
        while (std::getline(maps, line)) {
            if (line.find("libllama") != std::string::npos || line.find("libggml") != std::string::npos) {
                output["loaded_library_mappings"].push_back(line);
            }
        }
        for (const auto & task : config["cases"]) {
            std::vector<llama_token> prompt = task.contains("prompt_tokens")
                ? task["prompt_tokens"].get<std::vector<llama_token>>() : tokenize(vocab, task.at("prompt"));
            int count = task.value("generate_tokens", 48);
            require(count >= 1 && count <= 128, "Trace generation limit must be between 1 and 128");
            require(!prompt.empty() && prompt.size() <= 1536, "Invalid prompt token count");
            for (auto token : prompt) require(token >= 0 && token < n_vocab, "Invalid prompt token");
            std::vector<llama_token> trace = task.contains("continuation_tokens")
                ? task["continuation_tokens"].get<std::vector<llama_token>>() : generate_trace(model.get(), prompt, count, flash);
            require(!trace.empty() && trace.size() <= 128, "Invalid continuation token count");
            for (auto token : trace) require(token >= 0 && token < n_vocab, "Invalid continuation token");
            auto reference = evaluate(model.get(), prompt, trace, 1, flash);
            json result = {{"id", task.at("id")}, {"prompt_tokens", prompt}, {"continuation_tokens", trace},
                           {"reference", reference.receipt}, {"comparisons", json::array()}};
            auto widths = config.value("widths", std::vector<int>{2, 4, 8});
            require(!widths.empty() && widths.size() <= 6, "Invalid width count");
            for (int width : widths) {
                auto candidate = evaluate(model.get(), prompt, trace, width, flash);
                auto comparison = compare(reference, candidate);
                comparison["width"] = width;
                comparison["evaluation"] = candidate.receipt;
                result["comparisons"].push_back(comparison);
                std::cout << json({{"case", task.at("id")}, {"width", width},
                    {"different_argmax_rows", comparison["different_argmax_rows"]},
                    {"different_logit_rows", comparison["different_logit_rows"]}}).dump() << std::endl;
            }
            auto restored = evaluate(model.get(), prompt, trace, 1, flash);
            result["restored"] = restored.receipt;
            result["repeat_control"] = compare(reference, restored);
            output["cases"].push_back(result);
        }
        output["status"] = "completed";
        std::ofstream file(argv[3]);
        require(bool(file), "Cannot write result");
        file << output.dump(2) << '\n';
        require(bool(file), "Cannot finish result write");
        return 0;
    } catch (const std::exception & error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
