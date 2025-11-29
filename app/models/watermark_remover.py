import torch
import torch.nn as nn

class WatermarkRemover(nn.Module):
    def __init__(self):
        super(WatermarkRemover, self).__init__()
        self.enc1 = self.conv_block(3, 64)
        self.enc2 = self.conv_block(64, 128)
        self.enc3 = self.conv_block(128, 256)
        self.enc4 = self.conv_block(256, 512)

        self.bottleneck = self.conv_block(512, 1024)

        self.dec4 = self.conv_block(1024 + 512, 512)
        self.dec3 = self.conv_block(512 + 256, 256)
        self.dec2 = self.conv_block(256 + 128, 128)
        self.dec1 = self.conv_block(128 + 64, 64)

        self.final_layer = nn.Conv2d(64, 3, kernel_size=1)

    def conv_block(self, in_channels, out_channels):
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(nn.MaxPool2d(2)(e1))
        e3 = self.enc3(nn.MaxPool2d(2)(e2))
        e4 = self.enc4(nn.MaxPool2d(2)(e3))

        b = self.bottleneck(nn.MaxPool2d(2)(e4))

        d4 = self.dec4(torch.cat((nn.Upsample(scale_factor=2)(b), e4), dim=1))
        d3 = self.dec3(torch.cat((nn.Upsample(scale_factor=2)(d4), e3), dim=1))
        d2 = self.dec2(torch.cat((nn.Upsample(scale_factor=2)(d3), e2), dim=1))
        d1 = self.dec1(torch.cat((nn.Upsample(scale_factor=2)(d2), e1), dim=1))

        return self.final_layer(d1)