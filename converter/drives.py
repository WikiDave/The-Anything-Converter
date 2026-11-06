"""Drives: list USB sticks, hard disks, SSDs and CD/DVD drives, check their health and format them safely.

Safety rules (enforced here, not only in the interface):
- the disk with the operating system, the boot disk and any disk holding a mounted system folder are never formatted;
- internal disks only when the caller explicitly allows internal disks;
- the caller must repeat the exact device name as confirmation (e.g. "disk4", "/dev/sdb", "2").
Formatting is done with the operating system's own tools (diskutil, PowerShell Storage cmdlets, mkfs/parted).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .util import NO_WINDOW, ConversionError, human_size

FILESYSTEMS = {
    "exfat": "exFAT (USB sticks and big files; Windows, Mac and Linux)",
    "fat32": "FAT32 (old devices, cars, TVs; max 4 GB per file)",
    "ntfs": "NTFS (Windows disks)",
    "ext4": "ext4 (Linux)",
    "apfs": "APFS (Mac)",
    "hfs+": "Mac OS Extended (older Macs, Time Machine)",
}
FS_PER_OS = {"win32": ["exfat", "fat32", "ntfs"], "darwin": ["exfat", "fat32", "apfs", "hfs+"],
             "linux": ["exfat", "fat32", "ntfs", "ext4"]}


def filesystems_for(platform: str = sys.platform) -> list[list[str]]:
    return [[k, FILESYSTEMS[k]] for k in FS_PER_OS.get(platform, FS_PER_OS["linux"])]


SYSTEM_MOUNTS = {"/", "/boot", "/boot/efi", "/usr", "/var", "/home", "/System/Volumes/Data", "/System/Volumes/Preboot",
                 "/System/Volumes/VM", "[SWAP]"}


@dataclass
class Drive:
    id: str                  # what the OS calls it: /dev/sdb, disk4, 2 (Windows disk number), /dev/sr0
    name: str                # model / friendly name
    size: int
    bus: str = ""            # usb, sata, nvme, optical, ...
    kind: str = "disk"       # disk or optical
    removable: bool = False
    system: bool = False     # holds the running system or boots it: never formattable
    mounts: list[str] = field(default_factory=list)
    filesystems: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    rotational: bool | None = None
    serial: str = ""
    health: str = ""         # quick status from the OS (Windows/mac), if any

    def public(self) -> dict:
        d = asdict(self)
        d["size_text"] = human_size(self.size) if self.size else "no medium"
        d["can_format"], d["why_not"] = formattable(self)
        return d


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          **NO_WINDOW)


def _powershell(script: str, timeout: int = 60) -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
    r = _run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout)
    if r.returncode != 0:
        raise ConversionError((r.stderr or r.stdout).strip()[:500] or "PowerShell failed.")
    return r.stdout


# --------------------------------------------------------------------------- listing

def list_drives() -> list[Drive]:
    if sys.platform == "win32":
        return _list_windows()
    if sys.platform == "darwin":
        return _list_mac()
    return _list_linux()


def parse_lsblk(data: dict) -> list[Drive]:
    out = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") not in ("disk", "rom") or str(dev.get("name", "")).startswith(("zram", "loop", "ram")):
            continue
        mounts, fss, labels = [], [], []

        def walk(node):
            mounts.extend(m for m in (node.get("mountpoints") or []) if m)
            if node.get("fstype"):
                fss.append(node["fstype"])
            if node.get("label"):
                labels.append(node["label"])
            for ch in node.get("children") or []:
                walk(ch)
        walk(dev)
        optical = dev.get("type") == "rom"
        name = " ".join(x for x in (dev.get("vendor"), dev.get("model")) if x and not str(x).startswith("0x")).strip()
        out.append(Drive(id=dev.get("path") or "/dev/" + dev["name"], name=name or dev["name"],
                         size=int(dev.get("size") or 0), bus="optical" if optical else (dev.get("tran") or ""),
                         kind="optical" if optical else "disk",
                         removable=bool(dev.get("rm") or dev.get("hotplug") or dev.get("tran") == "usb"),
                         system=any(m in SYSTEM_MOUNTS for m in mounts), mounts=mounts, filesystems=fss,
                         labels=labels, rotational=dev.get("rota"), serial=dev.get("serial") or ""))
    return out


def _list_linux() -> list[Drive]:
    if not shutil.which("lsblk"):
        if "bsd" in sys.platform or "dragonfly" in sys.platform:
            raise ConversionError("Listing and formatting drives is not available on BSD yet "
                                  "(use 'geom disk list' and 'smartctl -a <disk>').")
        raise ConversionError("lsblk was not found (install util-linux).")
    r = _run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,MODEL,VENDOR,TRAN,RM,HOTPLUG,TYPE,MOUNTPOINTS,FSTYPE,LABEL,"
                                         "ROTA,SERIAL"])
    if r.returncode != 0:  # older lsblk: MOUNTPOINT instead of MOUNTPOINTS
        r = _run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,MODEL,VENDOR,TRAN,RM,HOTPLUG,TYPE,MOUNTPOINT,FSTYPE,LABEL,"
                                             "ROTA,SERIAL"])
        data = json.loads(r.stdout or "{}")

        def fix(node):
            node["mountpoints"] = [node.get("mountpoint")]
            for ch in node.get("children") or []:
                fix(ch)
        for d in data.get("blockdevices", []):
            fix(d)
        return parse_lsblk(data)
    return parse_lsblk(json.loads(r.stdout or "{}"))


def _list_mac() -> list[Drive]:
    import plistlib
    listing = plistlib.loads(_run(["diskutil", "list", "-plist", "physical"]).stdout.encode())
    out = []
    for whole in listing.get("WholeDisks", []):
        info = plistlib.loads(_run(["diskutil", "info", "-plist", whole]).stdout.encode() or b"<plist><dict/></plist>")
        entry = next((d for d in listing.get("AllDisksAndPartitions", []) if d.get("DeviceIdentifier") == whole), {})
        mounts, fss, labels = [], [], []
        for p in entry.get("Partitions", []) + entry.get("APFSVolumes", []):
            if p.get("MountPoint"):
                mounts.append(p["MountPoint"])
            if p.get("VolumeName"):
                labels.append(p["VolumeName"])
            if p.get("Content"):
                fss.append(p["Content"])
        internal = bool(info.get("Internal"))
        # the APFS container that holds the running system lives on the internal boot disk
        boot = internal and (info.get("BusProtocol") in ("Apple Fabric", "PCI-Express", "SATA", "NVMe")) and \
            any(m in ("/", "/System/Volumes/Data") for m in mounts) or info.get("SystemImage", False)
        out.append(Drive(id=whole, name=info.get("MediaName") or info.get("IORegistryEntryName") or whole,
                         size=int(info.get("TotalSize") or info.get("Size") or 0),
                         bus=str(info.get("BusProtocol") or "").lower(), removable=not internal or
                         bool(info.get("RemovableMedia") or info.get("Ejectable")),
                         system=bool(boot) or whole == _mac_boot_disk(), mounts=mounts, filesystems=fss,
                         labels=labels, rotational=None if info.get("SolidState") is None else not info["SolidState"],
                         health=str(info.get("SMARTStatus") or "")))
    # optical drives are not "physical" disks in diskutil's list; drutil knows them
    if shutil.which("drutil"):
        st = _run(["drutil", "status"]).stdout
        if "Vendor" in st:
            name = " ".join(re.findall(r"(?:Vendor|Product)\s+(\S.*?)\s{2,}", st)) or "CD/DVD drive"
            out.append(Drive(id="optical", name=name.strip(), size=0, bus="optical", kind="optical", removable=True,
                             filesystems=["no disc"] if "No Media" in st else []))
    return out


_boot_cache: str | None = None


def _mac_boot_disk() -> str:
    global _boot_cache
    if _boot_cache is None:
        import plistlib
        try:
            info = plistlib.loads(_run(["diskutil", "info", "-plist", "/"]).stdout.encode())
            _boot_cache = str(info.get("ParentWholeDisk") or "")
            # APFS: the system volume sits in a synthesized disk; its physical store is the real boot disk
            store = plistlib.loads(_run(["diskutil", "apfs", "list", "-plist"]).stdout.encode())
            for c in store.get("Containers", []):
                if c.get("ContainerReference") == _boot_cache and c.get("PhysicalStores"):
                    _boot_cache = re.sub(r"s\d+$", "", c["PhysicalStores"][0].get("DeviceIdentifier", _boot_cache))
        except Exception:  # noqa: BLE001
            _boot_cache = "disk0"
    return _boot_cache


def _list_windows() -> list[Drive]:
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$disks = Get-Disk | ForEach-Object {
  $d = $_
  $parts = Get-Partition -DiskNumber $d.Number
  $vols = $parts | Get-Volume
  [pscustomobject]@{
    Number = $d.Number; Name = $d.FriendlyName; Size = $d.Size; Bus = [string]$d.BusType
    IsSystem = $d.IsSystem; IsBoot = $d.IsBoot; Health = [string]$d.HealthStatus; Serial = $d.SerialNumber
    Letters = @($parts | Where-Object DriveLetter | ForEach-Object { [string]$_.DriveLetter + ':' })
    Fs = @($vols | ForEach-Object { $_.FileSystem }); Labels = @($vols | ForEach-Object { $_.FileSystemLabel })
    Media = [string](Get-PhysicalDisk | Where-Object DeviceId -eq $d.Number).MediaType
  }
}
$cd = Get-CimInstance Win32_CDROMDrive | ForEach-Object {
  [pscustomobject]@{ Drive = $_.Drive; Name = $_.Caption; Loaded = $_.MediaLoaded; Size = $_.Size }
}
[pscustomobject]@{ Disks = @($disks); Optical = @($cd) } | ConvertTo-Json -Depth 4 -Compress
"""
    data = json.loads(_powershell(script) or "{}")
    return parse_windows(data, os.environ.get("SystemDrive", "C:"))


def parse_windows(data: dict, system_drive: str = "C:") -> list[Drive]:
    out = []
    disks = data.get("Disks") or []
    if isinstance(disks, dict):
        disks = [disks]
    for d in disks:
        letters = [x for x in (d.get("Letters") or []) if x]
        bus = str(d.get("Bus") or "").lower()
        out.append(Drive(id=str(d.get("Number")), name=d.get("Name") or f"Disk {d.get('Number')}",
                         size=int(d.get("Size") or 0), bus=bus, removable=bus in ("usb", "sd", "mmc"),
                         system=bool(d.get("IsSystem") or d.get("IsBoot")) or system_drive.upper() in
                         [x.upper() for x in letters], mounts=letters,
                         filesystems=[x for x in d.get("Fs") or [] if x], labels=[x for x in d.get("Labels") or [] if x],
                         rotational=None if not d.get("Media") else d.get("Media") == "HDD",
                         serial=str(d.get("Serial") or "").strip(), health=str(d.get("Health") or "")))
    optical = data.get("Optical") or []
    if isinstance(optical, dict):
        optical = [optical]
    for c in optical:
        out.append(Drive(id=str(c.get("Drive") or "?"), name=c.get("Name") or "CD/DVD drive",
                         size=int(c.get("Size") or 0), bus="optical", kind="optical", removable=True,
                         mounts=[c["Drive"]] if c.get("Drive") else [],
                         filesystems=[] if c.get("Loaded") else ["no disc"]))
    return out


def formattable(d: Drive, allow_internal: bool = False) -> tuple[bool, str]:
    if d.system:
        return False, "this disk holds or boots the running system"
    if d.kind == "optical":
        return True, ""
    if not d.size:
        return False, "no medium in the drive"
    if not d.removable and not allow_internal:
        return False, "internal disk: allow internal disks first (tick the box, or --internal)"
    return True, ""


def find(drive_id: str) -> Drive:
    for d in list_drives():
        if d.id == drive_id:
            return d
    raise ConversionError(f"Drive {drive_id} was not found (unplugged?). Refresh the list.")


# --------------------------------------------------------------------------- health

def health(drive_id: str) -> dict:
    """SMART data and a verdict: OK, WARNING or FAILING (or UNKNOWN when the drive does not report it)."""
    d = find(drive_id)
    report: dict = {"drive": d.public(), "verdict": "UNKNOWN", "lines": [], "source": ""}
    lines = report["lines"]
    if d.kind == "optical":
        report["verdict"] = "N/A"
        lines.append("CD/DVD drives do not report health. Disc present: " +
                     ("no" if "no disc" in d.filesystems else "yes"))
        return report
    smart = _smartctl(d)
    if smart:
        report.update(smart)
    elif sys.platform == "win32":
        report.update(_health_windows(d))
    elif sys.platform == "darwin":
        st = d.health or "Not Supported"
        report["source"] = "diskutil"
        report["verdict"] = {"Verified": "OK", "Failing": "FAILING"}.get(st, "UNKNOWN")
        lines.append(f"SMART status: {st}")
    if not smart:
        lines.append("Tip: install smartmontools for full details (temperature, hours, wear, bad sectors): "
                     + ("winget install smartmontools" if sys.platform == "win32" else
                        "brew install smartmontools" if sys.platform == "darwin" else
                        "sudo apt install smartmontools"))
    for m in d.mounts:
        try:
            u = shutil.disk_usage(m if not re.fullmatch(r"[A-Za-z]:", m) else m + "\\")
            lines.append(f"{m}: {human_size(u.used)} used of {human_size(u.total)} ({u.used / u.total:.0%}), "
                         f"{human_size(u.free)} free")
        except OSError:
            pass
    return report


def _smartctl(d: Drive) -> dict | None:
    exe = shutil.which("smartctl")
    if not exe:
        return None
    dev = d.id if not d.id.isdigit() else f"/dev/pd{d.id}"
    if sys.platform == "darwin":
        dev = "/dev/" + d.id
    r = _run([exe, "-j", "-a", dev], 60)
    try:
        j = json.loads(r.stdout or "{}")
    except ValueError:
        return None
    if not j.get("device"):
        return None
    lines = []
    passed = (j.get("smart_status") or {}).get("passed")
    verdict = "OK" if passed else "FAILING" if passed is False else "UNKNOWN"
    if j.get("model_name"):
        lines.append(f"Model: {j['model_name']}  ·  serial {j.get('serial_number', '?')}  ·  firmware {j.get('firmware_version', '?')}")
    if passed is not None:
        lines.append("SMART self-assessment: " + ("PASSED" if passed else "FAILED — back up this disk now"))
    if (j.get("temperature") or {}).get("current") is not None:
        t = j["temperature"]["current"]
        lines.append(f"Temperature: {t} °C" + (" (hot)" if t >= 60 else ""))
    if (j.get("power_on_time") or {}).get("hours") is not None:
        h = j["power_on_time"]["hours"]
        lines.append(f"Powered on: {h} hours (~{h / 24 / 365:.1f} years)")
    if j.get("power_cycle_count") is not None:
        lines.append(f"Power cycles: {j['power_cycle_count']}")
    nv = j.get("nvme_smart_health_information_log") or {}
    if nv:
        lines.append(f"Wear: {nv.get('percentage_used', '?')}% of rated life used · spare {nv.get('available_spare', '?')}%")
        lines.append(f"Media errors: {nv.get('media_errors', 0)} · unsafe shutdowns: {nv.get('unsafe_shutdowns', 0)}")
        if nv.get("media_errors") or (nv.get("percentage_used") or 0) >= 90 or nv.get("critical_warning"):
            verdict = "WARNING" if verdict == "OK" else verdict
    bad = {5: "Reallocated sectors", 187: "Uncorrectable errors", 197: "Pending sectors", 198: "Offline uncorrectable",
           199: "Cable/CRC errors", 177: "Wear levelling count", 231: "SSD life left", 233: "Media wearout"}
    for a in (j.get("ata_smart_attributes") or {}).get("table", []):
        if a.get("id") in bad:
            raw = (a.get("raw") or {}).get("value", 0)
            lines.append(f"{bad[a['id']]}: {raw} (normalised {a.get('value')}/{a.get('thresh')})")
            if a["id"] in (5, 187, 197, 198) and raw:
                verdict = "WARNING" if verdict == "OK" else verdict
            if a.get("when_failed"):
                verdict = "FAILING"
    return {"verdict": verdict, "lines": lines, "source": "smartctl"}


def _health_windows(d: Drive) -> dict:
    lines = [f"Windows health status: {d.health or 'unknown'}"]
    verdict = {"Healthy": "OK", "Warning": "WARNING", "Unhealthy": "FAILING"}.get(d.health, "UNKNOWN")
    try:
        out = _powershell(
            f"$p = Get-PhysicalDisk | Where-Object DeviceId -eq {int(d.id)}; "
            "$c = $p | Get-StorageReliabilityCounter; "
            "[pscustomobject]@{Temp=$c.Temperature; Max=$c.TemperatureMax; Hours=$c.PowerOnHours; Wear=$c.Wear; "
            "ReadErr=$c.ReadErrorsTotal; WriteErr=$c.WriteErrorsTotal; Media=[string]$p.MediaType; "
            "Op=[string]$p.OperationalStatus} | ConvertTo-Json -Compress")
        c = json.loads(out or "{}")
        if c.get("Media"):
            lines.append(f"Type: {c['Media']} · operational status: {c.get('Op')}")
        if c.get("Temp"):
            lines.append(f"Temperature: {c['Temp']} °C (max {c.get('Max') or '?'} °C)")
        if c.get("Hours") is not None:
            lines.append(f"Powered on: {c['Hours']} hours")
        if c.get("Wear") is not None:
            lines.append(f"Wear: {c['Wear']}%")
            if c["Wear"] >= 90 and verdict == "OK":
                verdict = "WARNING"
        if c.get("ReadErr") or c.get("WriteErr"):
            lines.append(f"Read errors: {c.get('ReadErr') or 0} · write errors: {c.get('WriteErr') or 0}")
            if verdict == "OK":
                verdict = "WARNING"
    except (ConversionError, ValueError, subprocess.SubprocessError):
        lines.append("(Detailed counters need the app to run as administrator, or are not supported by this disk.)")
    return {"verdict": verdict, "lines": lines, "source": "Windows Storage"}


# --------------------------------------------------------------------------- format

def _clean_label(label: str, fs: str) -> str:
    label = re.sub(r"[^\w .-]", "", label or "").strip() or "USB"
    return (label.upper()[:11] if fs == "fat32" else label[:32 if fs in ("ext4", "apfs", "hfs+", "ntfs") else 15])


def plan_format(d: Drive, fs: str, label: str, full: bool, platform: str = sys.platform) -> list[list[str]]:
    """The commands that will run (also shown to the user before they confirm)."""
    fs = fs.lower()
    label = _clean_label(label, fs)
    if d.kind == "optical":
        if platform == "darwin":
            return [["drutil", "erase", "full" if full else "quick"]]
        if platform == "win32":
            return [["powershell", "IMAPI2 erase", d.id, "full" if full else "quick"]]
        return [["xorriso", "-outdev", d.id, "-blank", "all" if full else "as_needed"]]
    if fs not in FILESYSTEMS:
        raise ConversionError(f"Unknown file system: {fs}. Choose: {', '.join(FILESYSTEMS)}.")
    if platform == "darwin":
        mac_fs = {"exfat": "ExFAT", "fat32": "MS-DOS FAT32", "apfs": "APFS", "hfs+": "JHFS+"}.get(fs)
        if not mac_fs:
            raise ConversionError(f"{fs.upper()} cannot be made on a Mac. Choose exFAT, FAT32, APFS or Mac OS Extended.")
        scheme = "GPT" if fs in ("apfs", "hfs+") else "MBR"
        cmds = [["diskutil", "zeroDisk", d.id]] if full else []
        return cmds + [["diskutil", "eraseDisk", mac_fs, label, scheme, d.id]]
    if platform == "win32":
        if fs not in ("exfat", "fat32", "ntfs"):
            raise ConversionError(f"Windows can only make exFAT, FAT32 or NTFS (not {fs}).")
        if fs == "fat32" and d.size > 32 * 1024 ** 3:
            raise ConversionError("Windows makes FAT32 only up to 32 GB. Choose exFAT for this disk.")
        return [["powershell", "Clear-Disk", d.id, "full" if full else "quick", fs, label]]
    # Linux
    mk = {"exfat": ["mkfs.exfat", "-n", label], "fat32": ["mkfs.vfat", "-F", "32", "-n", label],
          "ntfs": ["mkfs.ntfs", "-f", "-L", label], "ext4": ["mkfs.ext4", "-F", "-L", label]}.get(fs)
    if not mk:
        raise ConversionError(f"{fs.upper()} cannot be made on Linux here. Choose exFAT, FAT32, NTFS or ext4.")
    part = d.id + ("p1" if d.id[-1].isdigit() else "1")
    table = "gpt" if fs == "ext4" else "msdos"
    ptype = {"exfat": "ntfs", "ntfs": "ntfs", "fat32": "fat32", "ext4": "ext4"}[fs]  # parted: 0x07 for exFAT/NTFS
    cmds = [["umount", m] for m in d.mounts]
    cmds += [["wipefs", "-a", d.id]]
    if full:
        cmds += [["dd", "if=/dev/zero", f"of={d.id}", "bs=4M", "conv=fsync", "status=none"]]
    cmds += [["parted", "-s", d.id, "mklabel", table, "mkpart", "primary", ptype, "1MiB", "100%"],
             ["partprobe", d.id], ["udevadm", "settle"], mk + [part]]
    return cmds


def check_confirm(d: Drive, confirm: str) -> None:
    if (confirm or "").strip() != d.id:
        raise ConversionError(f"Confirmation does not match. Type exactly: {d.id}")


def format_drive(drive_id: str, fs: str, label: str, confirm: str, full: bool = False,
                 allow_internal: bool = False, progress=None) -> str:
    d = find(drive_id)
    ok, why = formattable(d, allow_internal)
    if not ok:
        raise ConversionError(f"Not formatted: {why}.")
    check_confirm(d, confirm)
    cmds = plan_format(d, fs, label, full)
    if progress:
        progress(0.05, "Formatting")
    if d.kind == "optical":
        _erase_optical(d, full)
    elif sys.platform == "win32":
        _format_windows(d, fs.lower(), _clean_label(label, fs.lower()), full)
    elif sys.platform == "darwin":
        for c in cmds:
            r = _run(c, 6 * 3600)
            if r.returncode != 0:
                raise ConversionError(f"{' '.join(c[:2])} failed: {(r.stderr or r.stdout).strip()[:400]}")
    else:
        _format_linux(cmds)
    if progress:
        progress(1.0, "Done")
    return f"{d.name} ({d.id}) is formatted as {FILESYSTEMS.get(fs.lower(), fs)}" + \
        (f' with the name "{_clean_label(label, fs.lower())}".' if d.kind != "optical" else ".")


def _format_linux(cmds: list[list[str]]) -> None:
    missing = sorted({c[0] for c in cmds if not shutil.which(c[0])} - {"partprobe", "udevadm"})
    if missing:
        raise ConversionError(f"Missing tools: {', '.join(missing)} (e.g. sudo apt install exfatprogs dosfstools "
                              "ntfs-3g parted).")
    script = "set -e\n" + "\n".join(" ".join(_q(x) for x in c) + (" || true" if c[0] in ("umount", "partprobe",
                                                                                           "udevadm") else "")
                                      for c in cmds) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(script)
    try:
        prefix = [] if os.geteuid() == 0 else (["pkexec"] if shutil.which("pkexec") and os.environ.get("DISPLAY")
                                               else ["sudo"])
        r = subprocess.run([*prefix, "sh", f.name], capture_output=True, text=True, timeout=6 * 3600)
        if r.returncode != 0:
            raise ConversionError("Formatting failed: " + (r.stderr or r.stdout).strip()[-400:])
    finally:
        os.unlink(f.name)


def _q(s: str) -> str:
    return s if re.fullmatch(r"[\w/=.:%+-]+", s) else "'" + s.replace("'", "'\\''") + "'"


def _format_windows(d: Drive, fs: str, label: str, full: bool) -> None:
    """Runs elevated (UAC prompt): wipe the partition table, one partition, format."""
    n = int(d.id)
    fs_name = {"exfat": "exFAT", "fat32": "FAT32", "ntfs": "NTFS"}[fs]
    label_ps = label.replace("'", "''")
    script = (f"$ErrorActionPreference='Stop'\n"
              f"$d = Get-Disk -Number {n}\n"
              f"if ($d.IsSystem -or $d.IsBoot) {{ throw 'system disk' }}\n"
              f"Clear-Disk -Number {n} -RemoveData -RemoveOEM -Confirm:$false\n"
              f"Initialize-Disk -Number {n} -PartitionStyle MBR -ErrorAction SilentlyContinue\n"
              f"$p = New-Partition -DiskNumber {n} -UseMaximumSize -AssignDriveLetter\n"
              f"Format-Volume -Partition $p -FileSystem {fs_name} -NewFileSystemLabel '{label_ps}' "
              f"{'-Full ' if full else ''}-Confirm:$false -Force | Out-Null\n")
    _elevated_powershell(script)


def _erase_optical(d: Drive, full: bool) -> None:
    if sys.platform == "darwin":
        r = _run(["drutil", "erase", "full" if full else "quick"], 3 * 3600)
        if r.returncode != 0:
            raise ConversionError("Erasing the disc failed: " + (r.stderr or r.stdout).strip()[:300])
    elif sys.platform == "win32":
        letter = d.id.rstrip(":\\")
        script = ("$ErrorActionPreference='Stop'\n$m = New-Object -ComObject IMAPI2.MsftDiscMaster2\n"
                  "$r = $null\nforeach ($id in $m) { $x = New-Object -ComObject IMAPI2.MsftDiscRecorder2; "
                  "$x.InitializeDiscRecorder($id); if ($x.VolumePathNames -contains '" + letter + ":\\') { $r = $x } }\n"
                  "if (-not $r) { throw 'drive not found' }\n"
                  "$e = New-Object -ComObject IMAPI2.MsftDiscFormat2Erase\n$e.Recorder = $r\n"
                  "$e.ClientName = 'AnythingConverter'\n$e.FullErase = $" + ("true" if full else "false") +
                  "\n$e.EraseMedia()\n")
        _elevated_powershell(script)
    else:
        exe = shutil.which("xorriso")
        if not exe:
            raise ConversionError("Erasing a CD/DVD needs xorriso (sudo apt install xorriso).")
        r = _run([exe, "-outdev", d.id, "-blank", "all" if full else "as_needed"], 3 * 3600)
        if r.returncode != 0:
            raise ConversionError("Erasing the disc failed (is it a rewritable RW disc?): " +
                                  (r.stderr or r.stdout).strip()[-300:])


def _elevated_powershell(script: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ps1 = Path(tmp) / "format.ps1"
        log = Path(tmp) / "result.txt"
        ps1.write_text("try {\n" + script + f"\n'OK' | Out-File -Encoding utf8 '{log}'\n}} catch {{ $_.Exception.Message "
                       f"| Out-File -Encoding utf8 '{log}' }}\n", encoding="utf-8-sig")
        _powershell(f"Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "
                    f"'-NoProfile','-ExecutionPolicy','Bypass','-File','{ps1}'", timeout=6 * 3600)
        result = log.read_text(encoding="utf-8-sig").strip() if log.exists() else "cancelled (no administrator permission)"
        if result != "OK":
            raise ConversionError(f"Formatting failed: {result}")
