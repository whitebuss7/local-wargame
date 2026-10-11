# LAN 3D Battle Arena

A 3D multiplayer FPS game built with **Python** and the **Ursina Engine**. Play with up to three players over a local network (LAN), choose unique characters, use different weapons, and compete to reach the kill limit first.

## Features

* **3-player LAN multiplayer** — Play with up to three computers on the same local network.
* **First-person combat** — Move, aim, shoot, jump, crouch, sprint, and slide.
* **Four weapons** — Pistol, AK-47, Shotgun, and Sniper Rifle.
* **Three unique characters** with different abilities:

  * **KANAT (Wing):** Can fly for a limited time.
  * **ŞİMŞEK (Lightning):** Moves extremely fast and can knock opponents back while sprinting.
  * **MAYMUN (Monkey):** Has extra health and can throw slippery bananas.
* **Grenades** — Cook and throw grenades with adjustable throwing power.
* **Pickups** — Collect items such as health, ammunition, and bombs.
* **Respawning system** — Return to the battle after being eliminated.
* **Custom 3D map** — Explore buildings, containers, cover, stairs, and a central platform.
* **Server-authoritative combat** — The host manages important gameplay events and player state.

## Built With

* Python 3
* [Ursina Engine](https://www.ursinaengine.org/)
* TCP sockets for LAN communication
* JSON for network messages

## Requirements

* Python 3.10 or later is recommended.
* Ursina Engine
* Windows or another operating system supported by Python and Ursina
* Up to three computers connected to the same local network

## Installation

### 1. Install Python

Download Python from [python.org](https://www.python.org/downloads/).

### 2. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

Replace `YOUR_USERNAME` and `YOUR_REPOSITORY` with your GitHub username and repository name.

Alternatively, download the repository as a ZIP file and extract it.

### 3. Install the dependency

```bash
python -m pip install ursina
```

### 4. Start the game

The script in this repository is named `wargame.py`.

**Option A — Start as the host**

```bash
python wargame.py host Player1
```

**Option B — Join an existing game**

```bash
python wargame.py join 192.168.1.20 Player2
```

Replace `192.168.1.20` with the host computer's local IP address.

**Option C — Start a dedicated server**

```bash
python wargame.py server
```

A dedicated server runs without the normal game window.

You can also run the script without arguments and follow its prompts:

```bash
python wargame.py
```

## Multiplayer Setup

1. Connect all computers to the same Wi-Fi network or wired LAN.
2. Install Python and Ursina on each computer that needs to run the game client.
3. Start the host using the `host` command.
4. Find the host computer's local IP address.
5. Start the other clients using the `join` command and the host's IP address.
6. Allow Python through the firewall for **private networks** if prompted.
7. The default game port is **TCP 5555**. Make sure the host's firewall allows the connection.
8. Select a character and press **Ready**.
9. The host can start the round when everyone is ready. If all three players are ready, the round starts automatically.

> **Note:** This setup is intended for a local network. Internet play outside the LAN may require additional network configuration.

## Controls

| Key                  | Action                                           |
| -------------------- | ------------------------------------------------ |
| `W` `A` `S` `D`      | Move                                             |
| `Space`              | Jump; hold toward an edge to climb               |
| `Left Shift`         | Sprint                                           |
| `C` / `Left Ctrl`    | Crouch; crouch while moving to slide             |
| Mouse                | Look around                                      |
| `Left Mouse Button`  | Shoot                                            |
| `Right Mouse Button` | Aim / use sniper scope                           |
| `1`                  | Pistol                                           |
| `2`                  | AK-47                                            |
| `3`                  | Shotgun                                          |
| `4`                  | Sniper Rifle                                     |
| Mouse Wheel          | Switch weapons                                   |
| `R`                  | Reload                                           |
| `G`                  | Throw a grenade; hold to increase throwing power |
| `F`                  | Use character ability                            |
| `Esc`                | Release the mouse / resume                       |

## Characters

| Character          | Health | Special Ability                                              |
| ------------------ | -----: | ------------------------------------------------------------ |
| KANAT (Wing)       | 100 HP | Fly for up to 7 seconds; 20-second cooldown                  |
| ŞİMŞEK (Lightning) | 100 HP | High sprint speed and a knockback charge; 20-second cooldown |
| MAYMUN (Monkey)    | 150 HP | Throw bananas that make opponents slip and fall              |

## Weapons

| Weapon       |        Damage | Magazine |
| ------------ | ------------: | -------: |
| Pistol       |            22 |       12 |
| AK-47        |            12 |       30 |
| Shotgun      | 10 per pellet |        6 |
| Sniper Rifle |            90 |        5 |

Weapon damage can vary with distance, and headshots deal additional damage. Values shown are the game's configured base values.

## How to Win

Eliminate opponents and earn kills. The first player to reach **10 kills** wins the round. Players can respawn during a match.

## Project Structure

```text
.
├── wargame.py
├── README.md
└── .gitignore
```

## Troubleshooting

* **`ModuleNotFoundError: No module named 'ursina'`** — Run `python -m pip install ursina`.
* **Cannot connect to the host** — Check that all computers are on the same LAN, verify the host IP, and allow TCP port `5555` through the host's private-network firewall.
* **The game window does not open** — Check the Python version, Ursina installation, and graphics drivers.
* **The server is full** — The game supports a maximum of three connected players.

## Contributing

Suggestions, bug reports, and improvements are welcome. Feel free to open an issue or submit a pull request.

## License

No license has been specified yet. Add a `LICENSE` file if you want to publish the project under a particular open-source license.
