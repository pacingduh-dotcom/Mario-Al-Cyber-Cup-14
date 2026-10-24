# CYBER QUIZ - AL CYBER CUP 14

A 2D cyber-pixel platformer: 5 levels (bosses on levels 4 and 5), Indonesian quiz/tips, procedural art and audio, persistent saves.
Written in Python + Pygame; packaged to a standalone Windows `.exe` with PyInstaller.

> **Status of this source drop:** the game logic is covered by headless tests (see *Testing*), but the
> `.exe` has **not** been built or visually play-tested yet - it was authored in a Linux sandbox without
> pygame/PyInstaller/Windows. Build it with one of the two methods below.

## Get the .exe (pick one)
**A. GitHub Actions (no Windows PC needed):** push this folder to a GitHub repo -> *Actions* ->
*Build Windows EXE* -> download the `MarioAlCyberCup14-windows` artifact. The workflow runs the tests,
builds, and launches the exe for 8 s to make sure it starts.

**B. On Windows 10/11:** install Python 3.10+ (64-bit, "Add to PATH"), then double-click `build_windows.bat`.
Result: `dist\MarioAlCyberCup14.exe` (single file, no Python needed to run it).

Run from source: `pip install -r requirements.txt` then `python main.py`.

## v2 changes: smoother, 120 FPS
* **Render interpolation**: physics runs at a fixed 120 Hz; player, enemies, boss, moving platforms and shots are drawn
  interpolated between steps, so motion is smooth at 120/144/240 Hz (no more judder when FPS != 120).
* Defaults: **120 FPS cap, VSYNC off**. FRAME LIMIT now offers 30/60/120/144/240/UNLIMITED. Old saves that still had the
  old defaults (60 FPS + VSYNC) are upgraded automatically. **F3** (or Settings -> SHOW FPS) shows an FPS counter.
* Precise frame limiter (sleep + short spin), 1 ms Windows timer resolution, DPI-aware window.
* Frame-rate independent camera/menu animations, cached text/overlay/fade surfaces, display-format background layers, GC freeze per level.
* Single-file exe: `build_windows.bat` -> `dist\MarioAlCyberCup14.exe` (PyInstaller `--onefile --windowed`).

## v3: key + quiz system, FPS meter, credits
* Every level hides a golden **KEY** (about 55% into the level). Touch it and a question pops up; type the answer + ENTER.
  Wrong = try again (hint after 2 tries), ESC = cancel (step off the key and back on to retry). The exit gate opens only with the key
  (boss levels: key AND boss defeated). Boss levels do not start the boss fight until you hold the key, so there is no soft-lock.
* 10 questions (Math, Physics, Geography, English Grammar, Civics, Math, Biology, Geography, English, Religion): neighbouring levels never share a subject.
  Questions/answers live in `cybercup/quiz.py` (several accepted spellings per answer).
* **FPS meter** (ON by default, F3 toggles) shows FPS, frame time (ms), 1% low, min and max with 3 decimals.
* Credits: **Revando** - Base Game Maker, Idea Maker, Design Maker. **Bramantya** - Developer, Maintainer, Game Optimizer.

## v4: floating keys, dev mode
* The KEY now **floats** high above a platform; two stepping stones lead up to it (jump challenge).
* Attack is now **T** (or J). Dash is Left Shift / C. The FPS meter is always visible (no option).
* Dev features: all levels selectable; pause menu gets **GET ALL KEYS** and **AUTO PLAY** (invincible pilot).
  Hotkeys in game: F5 key, F6 auto play.

## v5: hidden developer mode, remote admin removed, smaller FPS meter, credits
* **Remote admin removed.** No Firebase channel, key or network code remains; a leftover `remote.json` from old builds is deleted.
* Credits include **Radit - Tester**. The FPS meter is about 35 % of its former area.

## v6: welcome screen, leaderboard, sessions, gems, door animation
* **Welcome screen** (first screen of the game, also behind *PLAY GAME*): name field (1-16 characters, trimmed, saved in
  `save.json`, remembered on later launches, changeable on this screen or in Settings -> PLAYER NAME), START GAME, your last run
  and the leaderboard. All text is English (the key questions were translated too).
* **Runs and leaderboard.** START GAME begins a new run at Level 1; CONTINUE resumes the saved run; Level Select is practice and is
  never recorded. A run stores player, current/highest level, **active play time** (time while really playing: not paused, not in
  fades/door sequences, not dead, not in the developer panel) and completion time. The final level comes from `len(LEVELS)`.
  A run is *Completed* only when the real final level is cleared inside that run and no developer tool touched it.
  Ranking: completed first (fastest time), then unfinished by highest level, then less play time, then name. One row per player
  (best run). Developer-assisted runs are kept in the save but never ranked. The leaderboard is local to this PC/save file
  (no cross-device sync).
* **Session reset.** (Sejak v8: 10 s tanpa input = **auto logout**, lihat v8.) Sebelumnya level di-*reset* setelah
  **10 s without input/movement while actively playing**; a warning countdown shows for the last 5 s. Pause, quiz, fades, door
  sequences and the developer panel never count. The idle 10 s is subtracted from the run time. Resetting can never complete a run.
  Manual reset: Developer panel -> SYSTEM -> RESET SESSION (confirmation; marks the run developer-assisted).
* **Gems are spendable.** Gems (collected once per run) form the balance shown in the HUD. Pause menu: *BUY LIFE* (2 gems, only up to
  the difficulty's starting lives). After GAME OVER: *REVIVE* (2 gems, respawn at the last checkpoint with 1 life). Costs live in
  `cybercup/config.py` together with the AFK time and other tunables. Balance is checked before deducting.
* **Door animation.** Touching the open exit: the door leaves slide open, the player walks into the doorway and disappears, the
  camera glides to the door, "LEVEL n+1 >>" appears, then the screen fades to the result screen. Triggers once.
* **Hidden developer mode.** There is no icon, setting or menu. Type the secret code on the keyboard **while playing** (not in
  name/quiz fields, not paused): the screen fades to a fully blank frame, then the Developer Mode panel opens. Wrong codes do
  nothing; a second activation is ignored; the unlock is session-only (never saved). Panel: Up/Down, Left/Right/Enter, Q/E or Tab
  switch tabs, Esc/F10 closes. Tabs: GAMEPLAY (fly, noclip, god, infinite health, super jump, speed, teleport, reset position),
  MONSTERS (kill all, clear, freeze, disable spawning, reset), DEBUG (coords/speed, stats, entity counts, collision boxes, log,
  reset dev settings), SYSTEM (exit developer mode, reset session, get all keys, auto play, close). Exiting restores everything.
  *Infinite stamina is N/A: the game has no stamina system.*

## v7: bahasa Indonesia, bos tutorial, tombol beli nyawa
* **Seluruh teks game kini bahasa Indonesia**: menu, HUD, pengaturan, cara bermain, kredit, pesan, nama level/bos, dan **10 pertanyaan kuis
  beserta jawabannya** (`cybercup/quiz.py`; beberapa ejaan jawaban diterima, mis. "pohon beringin"/"beringin", "puasa"/"berpuasa").
  Panel developer tersembunyi dan overlay debug sengaja tetap bahasa Inggris.
* **Instruksi melawan bos.** Saat bos muncul, kartu "CARA MENGALAHKAN BOS" tampil 9 detik. Selama pertarungan, satu baris tips di bawah
  layar berubah mengikuti keadaan bos (bersiap / AWAS menembak / HINDARI tembakan & kolom api / INTI MENYALA - serang sekarang).
* **Beli nyawa dipindah dari menu pause ke HUD**: tombol "BELI NYAWA [B]" di ujung kanan atas saat bermain (klik mouse atau tekan **B**).
  Biaya tampil di tombol, ada dialog konfirmasi, dan gem hanya berkurang jika berhasil. Tombol redup bila nyawa penuh atau gem kurang.
* Perbaikan: `Game.run()` bentrok dengan data run (`self.run`); loop utama kini `Game.main_loop()`.

## v8: login unik, LOGOUT, auto logout, panel dev lewat kode
* **Nama pemain unik.** Setiap nama hanya bisa dipakai sekali (tanpa membedakan huruf besar/kecil). Nama yang sudah pernah terdaftar
  atau punya riwayat main ditolak ("Nama sudah dipakai"), jadi pemain baru tidak bisa memakai riwayat/progres pemain sebelumnya.
  Tidak ada yang "diingat" saat game dibuka: layar login selalu kosong. Daftar nama disimpan di `save.json` (`players`).
* **LOGOUT menggantikan MENU UTAMA** di menu jeda, layar GAME BERAKHIR dan layar kemenangan (dengan konfirmasi). Di menu utama,
  item pertama menjadi **LOGOUT** saat sudah login (dan **MAIN GAME** saat belum login). Logout menutup run (tetap tercatat di
  papan peringkat, tidak bisa dilanjutkan), menghapus dunia/level dari memori dan kembali ke layar login.
  LANJUTKAN hanya melanjutkan run milik pemain yang sedang login; ganti nama di Pengaturan tidak lagi mungkin.
* **Auto logout (diperbaiki; sejak v9 batasnya 2 menit).** Sebelumnya hanya mereset level dan hanya saat bermain, jadi tampak "tidak bekerja".
  Sekarang pemain yang login otomatis di-logout setelah tanpa input di layar mana pun (bermain, jeda, kuis, menu,
  layar hasil). Peringatan hitung mundur tampil 5 detik terakhir. Tidak dihitung: fade/animasi pintu, panel developer, autoplay.
  Waktu idle dikurangi dari waktu main. Konstanta: `AFK_SECS`, `AFK_WARN_SECS` di `config.py`.
* **Panel developer: ketik kode setiap kali.** Mengetik kode saat bermain membuka panel **setiap kali** (bukan hanya sekali untuk
  mengaktifkan). F10 tidak lagi membuka panel; Esc/F10 hanya menutupnya. Alat yang aktif tetap berjalan setelah panel ditutup
  sampai "EXIT DEVELOPER MODE", logout, atau mulai run baru.

* **Logout menyimpan data terakhir.** Run yang berhenti karena logout/auto logout tetap di papan peringkat dengan status **Keluar**
  (level terakhir dan waktu main tersimpan; hanya run berstatus alat developer yang tidak diperingkat). Run dengan 0 detik juga tampil.
* **Tombol LOGOUT di kanan atas** semua layar saat login (bukan hanya Esc), dengan konfirmasi. Tombol BELI NYAWA digeser ke kirinya.
* **Gerbang arena bos terkunci tanpa kunci.** Tembok magenta menutup pintu masuk arena sampai kunci diambil, jadi pemain tidak bisa
  masuk ke kotak bos lebih dulu (pesan: "PINTU ARENA TERKUNCI").
* **Alat developer (tab SYSTEM, hanya saat dev aktif):** DELETE LEADERBOARD (hapus semua run + daftar nama; run pemain yang sedang
  login dipertahankan), SAVE DEBUG DUMP TO TEMP FILE, DELETE TEMP FILES, TEMP FOLDER. Folder temp tidak di-hardcode:
  `<folder save>/temp`, bisa diganti dengan variabel lingkungan `CYBERCUP_TEMP_DIR`. Hapus temp hanya menghapus file buatan game
  (`cybercup-debug-*.txt`).

## v9: papan peringkat sementara (folder temp), buka langsung ke menu, tutorial level 1, auto logout 2 menit
* **Papan peringkat sementara.** Data papan peringkat (daftar run + daftar nama terpakai) kini disimpan di `temp/leaderboard.json`,
  yaitu folder `temp` **di folder tempat game diekstrak** (di sebelah `main.py` / `.exe`). Progres level, skor terbaik dan pengaturan
  tetap di `save.json` (folder data pengguna). Menghapus folder `temp` mengosongkan papan peringkat dan membebaskan semua nama.
  Folder dibuat otomatis. Jika folder game tidak bisa ditulis (mis. read-only), game memakai `<folder save>/temp`; variabel lingkungan
  `CYBERCUP_TEMP_DIR` menimpa lokasi. `save.json` lama yang masih berisi papan peringkat digabung otomatis lalu dipindah ke `temp`.
  File debug developer (`cybercup-debug-*.txt`) juga ditulis ke folder `temp` yang sama. `temp/` sudah ada di `.gitignore`.
* **Game selalu terbuka di menu utama** (MAIN GAME terpilih). Layar login (nama) muncul setelah memilih MAIN GAME.
* **Tutorial cara bermain di level 1.** Kartu "CARA BERMAIN" tampil di bawah layar selama 20 detik pertama di level 1
  (`TUTORIAL_SECS`): A/D atau panah = gerak, W/Spasi/Panah Atas = lompat, T/J = serang, Shift Kiri/C = meluncur, Esc/P = jeda, B = beli nyawa.
* **Auto logout 2 menit** (sebelumnya 10 detik), berlaku di semua layar termasuk saat menjawab pertanyaan kunci. Selama 30 detik
  terakhir muncul peringatan: "Aktivitas tidak terdeteksi! Logout otomatis akan dilakukan dalam X detik - tekan tombol apa saja".
  Atur di `cybercup/config.py` (`AFK_SECS`, `AFK_WARN_SECS`).

## Papan peringkat = file sementara (temp)
* Leaderboard dan daftar nama terpakai disimpan **hanya** di `temp/leaderboard.json` (folder `temp` di sebelah `main.py` / `.exe`;
  jika folder itu tidak bisa ditulis, game memakai `<folder save>/temp`). Variabel `CYBERCUP_TEMP_DIR` bisa mengganti lokasinya.
* **Hapus file/folder itu = riwayat ikut hilang**, termasuk saat game sedang terbuka: game memeriksa file tiap ~1 detik dan
  tidak pernah menulis ulang riwayat lama dari memori. Nama-nama yang dipakai ikut bebas lagi.
  Satu-satunya yang tersisa adalah pemain yang sedang login (sesinya berjalan terus).
* `save.json` **tidak pernah** menyimpan leaderboard. Jika `save.json` lama (versi sebelumnya) masih memuat `runs`/`players`,
  isinya diabaikan dan dibuang pada penyimpanan berikutnya, jadi tidak ada "jalan belakang" untuk memulihkan riwayat.
* Tidak ada data leaderboard yang ter-hardcode di kode; game baru selalu mulai dengan papan kosong.

## Latest changes: boss fairness, 10 s / 1 min auto logout, English UI, "i" help button
* **Boss hit window ("HIT ME!") is now safe.** Before, boss shots lived 4 s, so shots/fire columns covered 100 % of the window in
  which you were told to attack. Now the attack lasts exactly as long as its hazards (shots 1.05 s, fire columns 0.65 s warning +
  0.4 s beam); when the core starts glowing every shot and column is removed, and touching the boss does no damage. The window
  itself is longer (3.0 s, was 2.4 s) and the wait between two windows is shorter (~2.1 s, was ~2.6 s). Timings: `entities.py`
  (`BOSS_*` constants).
* **Auto logout is two-tier** (`config.py`): **10 s** without gameplay input while actually playing (countdown banner for the last
  5 s); **1 minute** without any input in menus, the pause menu, the help panel, the key quiz and result screens (banner for the
  last 15 s). In gameplay only movement/action keys (arrows, WASD, Space, T/J, Shift/C, B, I, P/Esc) and mouse clicks count; unrelated
  keys and mouse movement do not. Fades, door animations, dialogs and the developer panel never count. Idle time is not play time.
* **The whole UI is English again; only the quiz questions (and their subjects) are Indonesian.**
* **How-to cards last 5 s, then shrink into an "i" button** (top-right corner, under the HUD bar). The level-1 how-to-play card and the
  boss-fight card both do this. Click the button or press **I** to open the full help panel (controls + how to beat a boss); the game
  is paused while it is open. I / Esc / click closes it.

## v10: simpler main menu, fullscreen
* The main menu now only has **PLAY GAME / LOGOUT, CARA BERMAIN, CREDITS, EXIT GAME**. LEVEL SELECT, CONTINUE and SETTINGS were removed from it
  (Settings is still reachable from the pause menu).
* The game **starts in fullscreen** every launch. **F11** toggles fullscreen/windowed on every screen (menus, name entry, quiz, gameplay).

## Controls
| Action | Keys |
|---|---|
| Move | Arrows or A / D |
| Jump (hold = higher) | Space / W / Up |
| Attack | T or J (or stomp from above) |
| Dash | Left Shift or C |
| Pause | Esc or P |
Menus: arrows + Enter, or mouse. Esc = back.

## Gameplay notes
Cyber gems 500 (coins were removed) (hidden on secret raised platforms), kill combos up to x5, time bonus, health bonus.
Bosses (levels 5, 7, 8, 9, 10) are only vulnerable while the core glows ("HIT ME!") after an attack: dodge the
telegraphed shots/floor columns, then stomp or strike. Levels 1-4 and 6 end at an exit gate.
Easy/Normal/Hard change hearts (5/3/2), lives (5/3/2) and enemy speed. Difficulty applies from the next level start.

## Saves & settings
`%APPDATA%\MarioAlCyberCup14\save.json` (progress, best score/time per level, settings). Missing or corrupted
files fall back to defaults. Crash details go to `crash.log` in the same folder.
No resolution picker is offered: the window is freely resizable and scales the fixed 1280x720 canvas.

## Troubleshooting
* **SmartScreen / antivirus warning:** unsigned PyInstaller exes are often flagged; choose "More info -> Run anyway",
  or build it yourself. * **No sound:** audio is synthesised at startup; if no audio device exists the game runs silently.
* **Low FPS:** Settings -> turn off VSYNC/PARTICLES/SCREEN SHAKE. * **Won't start:** read `crash.log` (see above).

## Testing
`python tests/test_logic.py` - physics, save system, damage/death/game-over, all 5 level layouts traversed by a
scripted bot, all boss fights resolved. `python tests/smoke_fake_pygame.py` - runs every screen against a pygame stub
(no real rendering). `python tests/smoke_real_pygame.py` - real pygame, headless (used in CI).

## Layout
`main.py` entry - `cybercup/` physics, levels (generator), entities, world (simulation), render, ui, audio, game,
devmode (developer menu), save_system - `build_windows.bat` + `.github/workflows` for packaging.
Licences: Pygame (LGPL), NumPy (BSD), PyInstaller (GPL + bootloader exception). All art/audio is original, generated in code.
