# grus-bringup

Xiaomi Mi 9 SE（grus，SDM712）上跑 UniXNU 的第一环：**让 U-Boot 在这台手机上起来**。

这个仓库只放**板级增量**，不含 U-Boot 源码。CI 每次去 clone `57UU/u-boot` 的
`sirius/v2.0` 分支（那是小米 8 SE 的 SDM710 支持，SoC 层和我们完全同源），
再把本仓库的文件叠进去。

## 为什么是 U-Boot，不是 EDK2 / Mu-Silicium

Mu-Silicium 全仓库搜 `sm6150` / `sdm710` / `sdm712` 是 0 命中，平台包得从零写一整个
EDK2 平台。而 `57UU/u-boot` 的 `sirius/v2.0` 直接用的 Linux 上游
`sdm670.dtsi` / `sdm710.dtsi` / `pm660.dtsi` / `pm660l.dtsi`，**SoC 层零移植**；
同一批 dts 里还有 `sdm710-xiaomi-pyxis.dts`（小米 CC9，1080×2340 + UFS 2.1），
和 grus 几乎同构，可以直接当模板。

## 目录

```
board/xiaomi/grus/
├── grus.config        Kconfig 片段，与 sirius.config 逐行相同
├── grus.env           默认环境：fastboot / 菜单 / 内存地址 / UFS 扫描
└── MAINTAINERS
dts/upstream/src/arm64/qcom/
└── sdm710-xiaomi-grus.dts   板级设备树，从 pyxis 派生，地址按真机实测改过
build.sh              构建脚本，board 名当参数，所以同一份脚本也能编 sirius 做对照
tools/mkbootimg.py    纯标准库的 boot.img 打包器（runner 上没有 mkbootimg）
```

## CI 产出

`uboot-<board>-<run>` 这个 artifact 里有：

| 文件 | 用途 |
|---|---|
| `u-boot-nodtb.bin` | U-Boot 裸二进制 |
| `u-boot-nodtb.bin.gz` | 上面那个的 gzip 流 |
| `sdm710-xiaomi-<board>.dtb` | 板级设备树 |
| `uboot-payload` | `gzip(u-boot-nodtb.bin) + dtb`，这就是 ABL 要的 kernel 槽格式 |
| `boot-<board>.img` | payload 套一层 v1 header |
| `build-<board>.log` | 完整编译日志，失败时也上传 |

## 为什么总同时编 sirius

sirius 是这个 fork 的原始目标板，**在真机上确认能起 U-Boot**。每次都顺带编一遍，
是为了让"编不过"这件事可诊断：sirius 也挂 → 工具链或分支的问题；只有 grus 挂 →
是我们的板级文件的问题。省这几分钟会让每次失败都变成猜谜。

## 真机上怎么用

`fastboot boot` 在这台机器上是被 ABL 拒的（连官方 TWRP 都报
`Failed to load/authenticate boot image`），所以走**刷 recovery 分区**这条路。

实测出来能过的组合只有一种，三个条件缺一不可：

1. header **v1**（v2 刷进 recovery 直接 3~5 秒回 fastboot，原厂 boot.img 也一样）；
2. kernel 槽 = `gzip 流 + DTB/QCDT`，gzip 流**长度精确等于原槽里的长度**，
   不能靠补零（补零会让解压器在零字节处断流）；
3. 原槽尾部的 QCDT 一个字节都不能动 —— 那是 ABL 挑设备树的来源，
   冲掉它硬件初始化不了，表现同样是静默回 fastboot。

具体做法见 `../probe-grus/` 的 `craft_exact_gz.py` 和 `pack_v1qcdt()`。

## 已知未核实项

设备树里这四个还是照抄 pyxis 的，首启（看到菜单）不需要，但真机验证时要对：

| 项 | 值 |
|---|---|
| UFS 复位 GPIO | tlmm 150 |
| 音量加键 | pm660l gpio 7 |
| USB ID 脚 | tlmm 38 |
| 面板 3.0V 使能 | tlmm 76 |

另外 `kernel_addr_r = 0x80080000` 是抄 sirius 的 —— U-Boot 自己就被 ABL 装在
0x80080000 附近，reloc 撞上会当场崩。这是第一个要调的值。
