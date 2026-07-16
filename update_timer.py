with open('/etc/systemd/system/trading-agent.timer', 'w') as f:
    f.write('''[Unit]
Description=Run Intelligent Invest Trading Cycle every 30 minutes during trading hours

[Timer]
OnCalendar=Mon-Fri *-*-* 09,10,11,12,13,14,15:00,30:00
Unit=trading-agent.service

[Install]
WantedBy=timers.target
''')
print("Successfully wrote trading-agent.timer")
