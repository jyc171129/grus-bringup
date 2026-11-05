#!/bin/bash
# Build U-Boot for a qcom SDM710 board (grus / sirius) out of the 57UU fork.
#
# Recipe taken verbatim from the fork's sirius-build.sh; only the board name is a
# parameter, so the same script produces the known-good sirius baseline as a
# control next to our grus port:
#
#   qcom_defconfig + qcom-phone.config + board/xiaomi/<board>/<board>.config
#   DEVICE_TREE = qcom/sdm710-xiaomi-<board>
#   payload     = gzip(u-boot-nodtb.bin) + <board>.dtb
#
# The payload layout matters: ABL treats the kernel slot as "optional gzip stream
# followed by one or more DTBs" and picks the one whose qcom,msm-id / qcom,board-id
# match the phone. That is exactly what the stock TWRP recovery image does, which is
# how we know it is the format this bootloader accepts.
#
# Usage:  ./build.sh [grus|sirius]      (default: grus)
# Env:    SRC  U-Boot source tree       (default: ./u-boot)
#         OUT  build directory          (default: ./out/<board>)
#         CROSS_COMPILE                 (default: aarch64-linux-gnu-)
set -euo pipefail

BOARD=${1:-grus}
SRC=${SRC:-$PWD/u-boot}
OUT=${OUT:-$PWD/out/$BOARD}
CROSS=${CROSS_COMPILE:-aarch64-linux-gnu-}
JOBS=${JOBS:-$(nproc)}
DT=${DEVICE_TREE:-qcom/sdm710-xiaomi-$BOARD}

[ -d "$SRC" ] || { echo "no U-Boot tree at $SRC" >&2; exit 1; }
[ -f "$SRC/board/xiaomi/$BOARD/$BOARD.config" ] || {
	echo "missing board fragment board/xiaomi/$BOARD/$BOARD.config" >&2; exit 1; }
[ -f "$SRC/dts/upstream/src/arm64/qcom/sdm710-xiaomi-$BOARD.dts" ] || {
	echo "missing board device tree sdm710-xiaomi-$BOARD.dts" >&2; exit 1; }

mkdir -p "$OUT"

echo "=== [1/3] defconfig + fragments ($BOARD) ==="
# Fragment files are resolved by basename from the source tree, the same way
# sirius-build.sh passes them.
make -C "$SRC" O="$OUT" CROSS_COMPILE="$CROSS" \
	qcom_defconfig qcom-phone.config "$BOARD.config"

echo "=== [2/3] build DEVICE_TREE=$DT ==="
make -C "$SRC" O="$OUT" CROSS_COMPILE="$CROSS" -j"$JOBS" DEVICE_TREE="$DT"

echo "=== [3/3] payload ==="
gzip -9 -c "$OUT/u-boot-nodtb.bin" > "$OUT/u-boot-nodtb.bin.gz"
DTB="$OUT/dts/upstream/src/arm64/qcom/sdm710-xiaomi-$BOARD.dtb"
if [ ! -f "$DTB" ]; then
	echo "missing $DTB; built DTBs were:" >&2
	find "$OUT/dts" -name '*.dtb' >&2 || true
	exit 1
fi
cat "$OUT/u-boot-nodtb.bin.gz" "$DTB" > "$OUT/uboot-payload"

ls -l "$OUT/u-boot-nodtb.bin" "$OUT/u-boot-nodtb.bin.gz" "$DTB" "$OUT/uboot-payload"
echo "UBOOT-$BOARD-DONE"
