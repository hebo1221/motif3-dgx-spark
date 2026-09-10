import pathlib,subprocess
p=pathlib.Path(__file__).resolve().parent
b='/opt/motif-work/motif3-tokenizer-runtime-baseline-v1'
subprocess.run(['g++','-O2','-std=c++17','-Wshadow=local','-Werror=shadow=local','-fPIC','-shared','loader.cpp','-isystem',b+'/ggml/include','-I'+b+'/vendor','-L',b+'/build/bin','-lggml-base','-ldl','-pthread','-o','loader.so'],cwd=p,check=True)
subprocess.run(['g++','-O2','-std=c++17','-Wshadow=local','-Werror=shadow=local','probe.cpp','-isystem',b+'/ggml/include','-isystem',b+'/include','-isystem',b+'/vendor','-L',b+'/build/bin','-lllama','-lggml','-lggml-base','-lggml-cpu','-ldl','-pthread','-o','probe'],cwd=p,check=True)
