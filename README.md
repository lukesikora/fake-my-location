# FML · Fake My Location

**Created by Luke Sikora**

Change your iPhone's location to anywhere in the world. Pick a spot on a map, tap **Teleport**, and your iPhone thinks it's there. You can even walk, bike, or drive to a new spot along real streets.

---

## ✅ What you need

- A **Mac** (any Mac from the last few years)
- An **iPhone**
- A **cable** to plug your iPhone into your Mac

> FML runs on your Mac. Your iPhone stays at the fake location **as long as FML is open on your Mac**.

---

## 📥 Install it (about 2 minutes)

You only do this once.

### Step 1: Open Terminal

Terminal is an app that's already on every Mac.

1. Press **⌘ Command + Space** on your keyboard (a search bar pops up).
2. Type **Terminal**.
3. Press **Return**.

A window with text opens. That's Terminal.

### Step 2: Copy this line

Hover over the gray box below and click the **copy button** (📋) on its right side.

```
curl -fsSL https://raw.githubusercontent.com/lukesikora/fake-my-location/main/install.sh | bash
```

### Step 3: Paste it into Terminal

1. Click inside the Terminal window.
2. Press **⌘ Command + V** to paste.
3. Press **Return**.

Wait until you see **✓ FML is installed!** FML then opens by itself in a new window and in your web browser.

> 💡 **If your Mac asks** *"Do you want the application python to accept incoming network connections?"*, click **Allow**. That lets your iPhone control FML.

You'll now have an **FML** icon on your Desktop. 🎉

---

## 📱 Set up your iPhone (first time only)

1. **Plug your iPhone into your Mac** with the cable.
2. **Unlock your iPhone.** If it asks **"Trust This Computer?"**, tap **Trust** and type your passcode.
3. In FML on your Mac, tap anywhere on the map, then click **Teleport**.
4. If FML says **Developer Mode is off**:
   1. On your iPhone, open **Settings** → **Privacy & Security**.
   2. Scroll all the way to the bottom and tap **Developer Mode**.
      *(Don't see it? Click **Teleport** in FML once more. FML makes the switch appear. Then close and reopen Settings.)*
   3. Turn it **on** and tap **Restart**.
   4. After your iPhone restarts, unlock it, tap **Turn On**, and enter your passcode.
5. Click **Teleport** in FML again. Your iPhone is now somewhere else! 🌍

---

## 🗺️ Using FML

1. **Double-click FML on your Desktop.** (Plug in your iPhone first.)
2. **Search for a place** at the top, or **tap anywhere on the map**.
3. Click **Teleport**. Done!

**Other things you can do:**

| Button | What it does |
|---|---|
| **Teleport** | Jumps your iPhone straight to that spot. |
| **Walk / Run / Bike / Drive** | Moves you there along real roads at that speed. (Teleport somewhere first.) |
| **⭐ Star** | Saves the place so you can go back with one tap. |
| **🌙 / ☀️** | Switches between light and dark. |
| **🎨** | Changes the color theme, including **Neon**. |
| **Back to Real Location** | Turns FML off and puts your iPhone back where it really is. |

**When you're done**, click **Back to Real Location**, or just close the FML Terminal window.

> ⚠️ **Keep the FML window open** while you're using a fake location. If you close it, unplug your iPhone, or your Mac goes to sleep, your iPhone goes back to its real location.

---

## 📲 Control it from your iPhone (optional)

When FML opens, the Terminal window shows a **QR code**.

1. Make sure your iPhone and Mac are on the **same Wi-Fi**.
2. Open the **Camera** app on your iPhone and point it at the QR code. Tap the link that pops up.
3. To make it look like an app: tap the **Share** button (□ with an arrow) → **Add to Home Screen** → **Add**.

Now you have an FML app icon on your iPhone. 🙌 *(Your Mac still has to have FML open.)*

> 🔒 That link has a secret code in it so nobody else on your Wi-Fi can move your phone. **Don't share it.**

---

## 🆘 Something not working?

| What you see | What to do |
|---|---|
| **"iPhone not found"** | Plug the iPhone in and unlock it. Still nothing? Try a **different cable**, because some cables only charge. |
| **"Look at your iPhone: tap Trust"** | Unlock your iPhone, tap **Trust**, and type your passcode. |
| **"Developer Mode is off"** | Follow step 4 in [Set up your iPhone](#-set-up-your-iphone-first-time-only). |
| **The page won't open on my iPhone** | Make sure both are on the same Wi-Fi. On your Mac, open **System Settings → Network → Firewall** and allow **python**. |
| **My location went back to normal** | FML closed, the cable came out, or your Mac fell asleep. Keep your Mac plugged into power with the lid open. |
| **"command not found" or another error while installing** | Copy the install line again and paste it into Terminal. Make sure you copied the **whole** line. |
| **The FML icon on my Desktop is gone** | Run the install line again. It brings it back. |

---

## 🔄 Update FML

Paste the **same install line** into Terminal again. Your saved places are kept.

```
curl -fsSL https://raw.githubusercontent.com/lukesikora/fake-my-location/main/install.sh | bash
```

## 🗑️ Uninstall FML

Close FML, then paste this into Terminal and press **Return**:

```
rm -rf ~/FML ~/Desktop/FML.command
```

---

## ⚠️ Heads up

- Some games (like **Pokémon GO**) and dating apps can tell when your location is faked and may **ban your account**.
- **Find My** and anyone you share your location with will see the fake location too.

---

<details>
<summary><b>How does it work? (for the curious)</b></summary>

iPhones don't let apps change your location, but they do let a Mac do it for testing. That's the same feature app developers use in Xcode. FML runs a small server on your Mac that uses [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) to talk to your iPhone. The map runs in your browser and works on your phone too. Maps are from [OpenFreeMap](https://openfreemap.org) and [OpenStreetMap](https://www.openstreetmap.org), and street routes come from [OSRM](https://project-osrm.org).

Everything is installed into `~/FML`. Nothing needs admin rights.

</details>
