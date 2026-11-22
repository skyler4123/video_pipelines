# Systemd

`comfyui.service` is a user-service template for a persistent ComfyUI worker.
It defaults to CPU mode and binds all interfaces because the workstation is
intended to be reached over the local network.

```bash
mkdir -p ~/.config/systemd/user
cp ops/systemd/comfyui.service ~/.config/systemd/user/comfyui.service
# Edit paths, and remove --cpu if this worker has a GPU.
systemctl --user daemon-reload
systemctl --user enable --now comfyui
journalctl --user -u comfyui -f
```

ComfyUI has no authentication. Restrict port `8188` with a firewall or a
private network/VPN. Do not forward it directly from the internet.

For foreground use, `bin/comfy` is the same checkout with a simpler lifecycle.
