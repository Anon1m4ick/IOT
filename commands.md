# TUI Commands (console control)

Type commands in the input at the bottom. Device-specific commands require the **pi1**, **pi2**, or **pi3** prefix.

---

## No prefix

| Command | Description |
|--------|-------------|
| **help** | Show command help |
| **quit** / **exit** | Exit the application |
| **sensors** | List sensors and status (Pi, simulated/real) |
| **actuators** | List actuators and status |

---

## PI1 — Door / Security / Camera

| Command | Description |
|--------|-------------|
| **pi1 dl on** | Turn door light (DL) on |
| **pi1 dl off** | Turn door light off |
| **pi1 dl status** | Door light status |
| **pi1 db activate** [frequency] [duration] | Activate buzzer (default 1000 Hz, 1 s) |
| **pi1 dms pin 1234** | Enter 4-digit PIN on DMS (use your PIN) |
| **pi1 camera status** | Camera status |
| **pi1 camera start** | Start camera stream |
| **pi1 camera stop** | Stop camera stream |
| **pi1 camera url** | Show camera stream URL |
| **pi1 alarm status** | Alarm status (active, armed, person count) |
| **pi1 alarm arm** | Arm security (10 s delay) |
| **pi1 alarm disarm** | Disarm and turn off alarm |
| **pi1 alarm trigger** [reason] | Manually trigger alarm |

---

## PI2 — Kitchen / Timer (4SD)

| Command | Description |
|--------|-------------|
| **pi2 4sd status** | Remaining time, running, blinking 00:00 |
| **pi2 4sd set** \<seconds\> | Set timer (e.g. `pi2 4sd set 120`) |
| **pi2 4sd start** | Start timer |
| **pi2 4sd stop** | Stop timer |
| **pi2 4sd add** [seconds] | Add seconds (if omitted, uses button_add_seconds from settings) |
| **pi2 4sd btn** | Simulate kitchen button press (add time / stop blinking) |
| **pi2 4sd blink** | Trigger test blink 00:00 |

---

## PI3 — Room / RGB (IR, BRGB)

| Command | Description |
|--------|-------------|
| **pi3 ir** \<0–9\> | Simulate remote button press (BRGB control) |

Remote buttons:
- **0** = OFF  
- **1** = WHITE  
- **2** = RED  
- **3** = GREEN  
- **4** = BLUE  
- **5** = YELLOW  
- **6** = PURPLE  
- **7** = LIGHT_BLUE  
- **8** = OFF  
- **9** = WHITE  
