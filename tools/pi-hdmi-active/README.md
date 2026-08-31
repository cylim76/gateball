# pi-hdmi-active

为 Raspberry Pi 4/5 的 KMS HDMI 音频提供：

- LG TV 文件 EDID，解决电视某些输入口无法返回 EDID/ELD 时没有声音的问题；
- HDMI0 与 HDMI1 的音频配置；
- 热插拔自动切换：HDMI0 有真实连接时优先 HDMI0，否则使用 HDMI1；
- PipeWire/WirePlumber 默认输出、音量与正在播放的流自动迁移；
- 可恢复的安装和卸载。

## 板卡安全

安装器只允许 Raspberry Pi 4、Raspberry Pi 5 和 Raspberry Pi 400。它在请求 `sudo` 或写入任何文件之前读取设备树；RK3566、普通 PC 和其他不支持的板卡会显示 `skipped safely`，以退出码 0 结束，不修改启动或音频配置。

Gateball 的总安装脚本不会自动运行本工具。请只在需要修复 HDMI 音频的 Raspberry Pi 上进入本目录手动安装，避免把板卡专用的启动配置混入 RK3566 的常规部署流程。

## 一键安装

以桌面用户运行，不要在命令前加 `sudo`：

```bash
cd ~/pi-hdmi-active
./install.sh --reboot
```

安装脚本会在需要时自行请求 `sudo`，更新 initramfs，并重启。

默认安装包内已经包含本次验证过的 LG TV EDID。如果换了另一台电视，先把电视接到能够正常返回 EDID 的输入口，再运行：

```bash
./install.sh --capture --reboot
```

## 自动切换规则

- 树莓派 HDMI0 实际接线：选择 HDMI0；
- HDMI0 未接线：选择 HDMI1；
- HDMI1 使用文件 EDID、强制热插拔和 1080p/60，避免电视 HDMI 输入口不返回 ELD；
- 切换后取消静音并将音量设为 60%。

## 状态和日志

```bash
~/.local/bin/pi-hdmi-active status
systemctl --user status pi-hdmi-active.service
journalctl --user -u pi-hdmi-active.service
```

也可以手动触发一次选择：

```bash
~/.local/bin/pi-hdmi-active once hdmi0
~/.local/bin/pi-hdmi-active once hdmi1
```

## 一键卸载

```bash
cd ~/pi-hdmi-active
./uninstall.sh --reboot
```

卸载会移除服务、EDID 和本工具添加的启动参数。启动参数备份保留在：

```text
/var/lib/pi-hdmi-active/backups
```

## 文件说明

- `install.sh`：安装服务、EDID、initramfs hook 和启动参数；
- `uninstall.sh`：卸载并保留备份；
- `pi-hdmi-active`：热插拔监控与音频切换程序；
- `systemd/pi-hdmi-active.service`：用户服务；
- `assets/lg-tv-edid.bin`：本次从 LG TV HDMI3 读取并验证的 EDID；
- `assets/initramfs-hook`：把 EDID 加入启动内存盘。
