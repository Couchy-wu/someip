import torch, torchvision, sys, os
import torchaudio

print('Python          :', sys.version.split()[0])
print('PyTorch version :', torch.__version__)
print('torchvision     :', torchvision.__version__)
print('CUDA available? :', torch.cuda.is_available())
print('CUDA version    :', torch.version.cuda)           # PyTorch 编译时的 CUDA 版本
print('torchaudio version    :', torchaudio.__version__)
