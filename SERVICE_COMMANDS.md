# ASSTROO Service Management

## Service Status
Check if services are running:
```bash
systemctl status userbot.service
systemctl status adminbot.service
```

## View Logs
Live logs (follow mode):
```bash
journalctl -u userbot.service -f
journalctl -u adminbot.service -f
```

Recent logs (last 50 lines):
```bash
journalctl -u userbot.service -n 50
journalctl -u adminbot.service -n 50
```

## Restart Services
After code or environment changes:
```bash
systemctl restart userbot.service adminbot.service
```

Or individually:
```bash
systemctl restart userbot.service
systemctl restart adminbot.service
```

## Stop Services
```bash
systemctl stop userbot.service adminbot.service
```

## Start Services
```bash
systemctl start userbot.service adminbot.service
```

## Disable Services
Prevent auto-start on boot:
```bash
systemctl disable userbot.service adminbot.service
```

## Enable Services
Enable auto-start on boot:
```bash
systemctl enable userbot.service adminbot.service
```

## Tmux Fallback (if systemd issues)
```bash
cd /root/ASSTROO
tmux new -s userbot 'source venv/bin/activate && python3 app/main.py'
tmux new -s adminbot 'source venv/bin/activate && python3 app/admin_main.py'
```

Detach: `Ctrl+b` then `d`
Reattach: `tmux attach -t userbot` or `tmux attach -t adminbot`
List sessions: `tmux ls`
Kill session: `tmux kill-session -t userbot`

