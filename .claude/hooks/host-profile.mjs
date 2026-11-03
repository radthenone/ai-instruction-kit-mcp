// Wspólna detekcja hosta VPS/local dla hooków (ADR-0011).
//
// Jedyne źródło reguły po stronie JS: używają jej server-guard.mjs i language-reminder.mjs.
// Parytet z `src/guides/host_profile.py` pilnuje test na tabeli `GUARD_*`.
// Zmienna `GUARD_*` pusta albo nieparsowalna = brak zmiennej → realny pomiar systemu.
// Hook nie wywołuje `kit-ai host` (ADR-0011).

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { cpus, platform as osPlatform } from "node:os";

export const VPS = "vps";
export const LOCAL = "local";

const SMALL_CPU_MAX = 2;
const SMALL_RAM_MAX_BYTES = 8 * 1024 ** 3;
const CI_VARS = ["GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "BUILDKITE", "CIRCLECI", "TRAVIS", "TF_BUILD"];
const DEV_CONTAINER_VARS = ["CODESPACES", "REMOTE_CONTAINERS"];
const DESKTOP_VARS = ["DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "DESKTOP_SESSION"];
const WSL_VARS = ["WSL_DISTRO_NAME", "WSL_INTEROP"];

const filled = (env, names) => names.some((v) => String(env[v] ?? "").trim() !== "");
const present = (env, name) => env[name] !== undefined && String(env[name]).trim() !== "";

// Liczba całkowita z `GUARD_*`; pusta lub nieparsowalna → null (brak zmiennej).
function guardInt(env, name) {
  if (!present(env, name)) return null;
  const s = String(env[name]).trim();
  return /^[+-]?[0-9]+$/.test(s) ? Number(s) : null;
}

// Flaga `GUARD_*`: `1` → true, `0` → false; inne wartości → null (brak zmiennej).
function guardFlag(env, name) {
  if (!present(env, name)) return null;
  const s = String(env[name]).trim();
  if (s === "1") return true;
  if (s === "0") return false;
  return null;
}

function normalizeOverride(value) {
  const key = String(value ?? "").trim().toLowerCase();
  return key === VPS || key === LOCAL ? key : null;
}

function readMeminfo() {
  try {
    let mem = null;
    let swap = null;
    for (const line of readFileSync("/proc/meminfo", "utf8").split("\n")) {
      const m = line.match(/^(MemTotal|SwapTotal):\s+(\d+)/);
      if (m) {
        if (m[1] === "MemTotal") mem = Number(m[2]) * 1024;
        else swap = Number(m[2]) * 1024;
      }
    }
    return { mem, swap };
  } catch {
    return { mem: null, swap: null };
  }
}

function procVersionIsWsl() {
  try {
    const version = readFileSync("/proc/version", "utf8").toLowerCase();
    return version.includes("microsoft") || version.includes("wsl");
  } catch {
    return false;
  }
}

function detectVirtLive() {
  try {
    return execFileSync("systemd-detect-virt", { encoding: "utf8", timeout: 5000 }).trim().toLowerCase();
  } catch (err) {
    // Na bare metal komenda wypisuje `none` z kodem ≠ 0.
    return String(err?.stdout || "").trim().toLowerCase();
  }
}

/**
 * Wykryj profil hosta: `vps` albo `local`.
 *
 * @param {Record<string, string | undefined>} env Zmienne (domyślnie `process.env`).
 * @param {object} real Pomiary systemu, nadpisywalne w testach. Brak pola → realny odczyt.
 * @param {string} [real.platform] Zamiast `os.platform()`.
 * @param {number} [real.cpuCount] Zamiast `os.cpus().length`.
 * @param {{mem: number|null, swap: number|null}} [real.meminfo] Zamiast `/proc/meminfo`.
 * @param {string} [real.virt] Zamiast `systemd-detect-virt`.
 * @param {boolean} [real.wsl] Zamiast `/proc/version`.
 * @returns {"vps" | "local"}
 */
export function detectHostProfile(env = process.env, real = {}) {
  const override = normalizeOverride(env.KIT_HOST_PROFILE) || normalizeOverride(env.GUIDES_HOST_PROFILE);
  if (override) return override;

  const plat = present(env, "GUARD_PLATFORM") ? env.GUARD_PLATFORM : (real.platform ?? osPlatform());
  if (!String(plat).startsWith("linux")) return LOCAL;

  const ci = guardFlag(env, "GUARD_IS_CI") ?? (["1", "true", "yes"].includes(String(env.CI ?? "").trim().toLowerCase()) || filled(env, CI_VARS));
  if (ci) return LOCAL;

  const wsl = guardFlag(env, "GUARD_IS_WSL") ?? (filled(env, WSL_VARS) || (real.wsl ?? procVersionIsWsl()));
  if (wsl) return LOCAL;

  // Codespaces / devcontainer: mały kontener bez desktopu, ale to stacja deweloperska.
  if (filled(env, DEV_CONTAINER_VARS)) return LOCAL;

  let cpu = guardInt(env, "GUARD_CPU_COUNT");
  if (cpu === null) {
    const measured = real.cpuCount ?? cpus().length;
    cpu = measured > 0 ? measured : null;
  }
  let mem = guardInt(env, "GUARD_MEM_BYTES");
  let swap = guardInt(env, "GUARD_SWAP_BYTES");
  if (mem === null || swap === null) {
    const live = real.meminfo ?? readMeminfo();
    mem ??= live.mem;
    swap ??= live.swap;
  }
  if (cpu === null || mem === null || swap === null) return LOCAL;
  if (!(cpu <= SMALL_CPU_MAX && mem <= SMALL_RAM_MAX_BYTES && swap === 0)) return LOCAL;

  const virt = present(env, "GUARD_VIRT")
    ? String(env.GUARD_VIRT).trim().toLowerCase()
    : (real.virt ?? detectVirtLive());
  const virtualized = Boolean(virt) && virt !== "none" && virt !== "unknown";
  const desktop = guardFlag(env, "GUARD_HAS_DESKTOP") ?? filled(env, DESKTOP_VARS);

  return virtualized || !desktop ? VPS : LOCAL;
}
