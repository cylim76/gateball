# ESP32 USB 433MHz 距离测试工具

这个工具通过 USB 串口监听 `esp32_433_bridge.ino` 输出的遥控器按键信息，适合给 RXB 接收板焊接天线后做距离测试。

## Windows 使用方法

1. 用可传输数据的 USB 线连接 ESP32 和电脑。
2. 关闭 Arduino 串口监视器及其他占用该 COM 口的软件。
3. 双击 `start_windows.bat`。
4. 工具会优先选择 CP2102、CH340 等 USB 串口；确认设备后点击“开始测试”。
5. 每成功解码一次，中央状态条会闪绿色。拿着遥控器逐步走远，并用相同频率反复按同一个按键。

首次运行缺少 `pyserial` 时，启动脚本会自动安装。也可以手动安装：

```powershell
py -3 -m pip install -r requirements.txt
```

如果系统没有 `py` 命令，也可以把上面的 `py -3` 换成 `python`。

然后运行：

```powershell
py -3 esp32_usb_range_test.py
```

也可以指定串口：

```powershell
py -3 esp32_usb_range_test.py --port COM5 --baud 115200
```

## GB2 / Ubuntu 使用方法

确保 GB2 已进入图形桌面，把 ESP32 接到 USB 后运行：

```bash
cd ~/gateball/tools/esp32-usb-range-test
chmod +x start_linux.sh
./start_linux.sh
```

脚本会检查并安装缺少的 `python3-tk`、`python3-serial`，优先选择 `/dev/serial/by-id/` 下的稳定设备路径，其次选择 `/dev/ttyUSB0`。`lucas` 用户需要属于 `dialout` 用户组；Gateball 安装脚本已经处理该权限。

图形工具不能直接显示在普通 SSH 终端中，需要在 GB2 本机桌面运行。若 Gateball 服务正在占用同一个 USB 串口，请先在设置中暂停遥控器监听，或临时停止 Gateball 服务，再打开测试工具。

## 测试结果

- **累计成功接收**：ESP32 成功解码并输出的信号总数。
- **最近 10 秒**：判断当前距离下是否仍在持续收到信号。
- **当前无信号时间**：距离过远或出现遮挡后会持续增加。
- **最长无信号时间**：本轮测试中两次成功接收之间的最长间隔。
- **成功接收记录**：显示原始码、遥控器地址、按键码、位数和基础脉宽。
- **串口原始输出**：用于检查 ESP32 启动信息或解码异常。
- 每次测试会在 `logs` 文件夹生成一个 UTF-8 CSV 文件。

## 关于“信号强度”

RXB 接收板和当前 ESP32 程序没有输出 RSSI/dBm，因此软件无法显示真实射频功率。这里显示的是**成功解码率的现场指标**。为了让不同距离的数据可比较，建议每个测试点：

1. 遥控器方向和高度保持一致。
2. 每秒按一次相同按键，共按 20 次。
3. 记录工具实际收到的次数，例如 `20/20`、`17/20`。
4. 分别测试无遮挡、隔墙和人体遮挡场景。

ESP32 固件会过滤不稳定帧并抑制 350ms 内的重复输出，所以不要在极短时间内连续快速按键。
