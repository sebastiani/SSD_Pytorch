# -*- coding: utf-8 -*-
# Written by yq_yao

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from utils.box_utils import weights_init

def add_extras(size, in_channel, batch_norm=False):
    # Extra layers added to resnet for feature scaling
    layers = []
    layers += [nn.Conv2d(in_channel, 256, kernel_size=1, stride=1)]
    layers += [nn.Conv2d(256, 256, kernel_size=3, stride=2, padding=1)]
    return layers

def conv3x3(in_planes, out_planes, stride=1):
    "3x3 convolution with padding"
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=1, bias=False)

class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = self.relu(out)

        return out

class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
                               padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out

def last_layer_trans():
    return nn.Sequential(nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1),
                  nn.ReLU(inplace=True),
                  nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1),
                  nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1))


def trans_layers(size):
    layers = list()
    layers += [nn.Sequential(nn.Conv2d(512, 256, kernel_size=3, stride=1,           padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1))]
    layers += [nn.Sequential(nn.Conv2d(1024, 256, kernel_size=3, stride=1,           padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1))]
    layers += [nn.Sequential(nn.Conv2d(512, 256, kernel_size=3, stride=1,           padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1))]

    return layers

def latent_layers(size):
    layers = []
    for i in range(3):
        layers += [nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1)]
    return layers

def up_layers(size):
    layers = []
    for i in range(3):
        layers += [nn.ConvTranspose2d(256, 256, kernel_size=2, stride=2, padding=0)]
    return layers


class RefineResnet(nn.Module):
    def __init__(self, block, num_blocks, size):
        super(RefineResnet, self).__init__()
        self.inplanes = 64

        self.conv1 = nn.Conv2d(3, 64, kernel_size=7,
                               stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)

        # Bottom-up layers
        self.layer1 = self._make_layer(block,  64, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(block, 128, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(block, 256, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(block, 512, num_blocks[3], stride=2)
        self.inchannel = block.expansion * 512
        self.extras = nn.ModuleList(add_extras(str(size), self.inchannel))
        self.smooth1 = nn.Conv2d(self.inchannel, 512, kernel_size=3, stride=1, padding=1)
        self.last_layer_trans = last_layer_trans()
        self.trans_layers = nn.ModuleList(trans_layers(str(size)))
        self.latent_layers = nn.ModuleList(latent_layers((str(size))))
        self.up_layers = nn.ModuleList(up_layers(str(size)))
        self._init_modules()

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def _init_modules(self):
        self.extras.apply(weights_init)
        self.smooth1.apply(weights_init)
        self.last_layer_trans.apply(weights_init)
        self.trans_layers.apply(weights_init)
        self.latent_layers.apply(weights_init)
        self.up_layers.apply(weights_init)

    def forward(self, x):
        # Bottom-up
        odm_sources = list()
        c1 = F.relu(self.bn1(self.conv1(x)))
        c1 = F.max_pool2d(c1, kernel_size=3, stride=2, padding=1)
        c2 = self.layer1(c1)
        c3 = self.layer2(c2)
        c4 = self.layer3(c3)
        c5 = self.layer4(c4)
        x = c5
        c5_ = self.smooth1(c5)
        arm_sources = [c3, c4, c5_]
        for k, v in enumerate(self.extras):
            x = F.relu(v(x), inplace=True)
            if k % 2 == 1:
                arm_sources.append(x)
        x = self.last_layer_trans(x)
        odm_sources.append(x)

        trans_layer_list = list()

        for(p, t) in zip(arm_sources, self.trans_layers):
            trans_layer_list.append(t(p))
      
        trans_layer_list.reverse()
        for (t, u, l) in zip(trans_layer_list, self.up_layers, self.latent_layers):
            x = F.relu(l(F.relu(u(x)+ t, inplace=True)), inplace=True)
            odm_sources.append(x)

        odm_sources.reverse()
        return arm_sources, odm_sources

# def RefineResnet18(size, channel_size='48'):
#     return RefineResnet(BasicBlock, [2, 2, 2, 2], size)

# def RefineResnet34(size, channel_size='48'):
#     return RefineResnet(BasicBlock, [3, 4, 6, 3], size)

def RefineResnet50(size, channel_size='48'):
    return RefineResnet(Bottleneck, [3, 4, 6, 3], size)

def RefineResnet101(size, channel_size='48'):
    return RefineResnet(Bottleneck, [3, 4, 23, 3], size)

def RefineResnet152(size, channel_size='48'):
    return RefineResnet(Bottleneck, [3, 8, 36, 3], size)

if __name__ == "__main__":
    import os
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    model3 = RefineResnet50(size=300)
    print(model3)
    with torch.no_grad():
        model3.eval()
        x = torch.randn(1, 3, 320, 320)
        model3.cuda()
        model3(x.cuda())
