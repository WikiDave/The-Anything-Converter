import pytest

from converter import drives
from converter.drives import Drive, check_confirm, formattable, parse_lsblk, parse_windows, plan_format
from converter.util import ConversionError

LSBLK = {"blockdevices": [
    {"name": "nvme0n1", "path": "/dev/nvme0n1", "size": 512e9, "model": "Samsung SSD", "tran": "nvme", "rm": False,
     "hotplug": False, "type": "disk", "mountpoints": [None], "children": [
         {"name": "nvme0n1p1", "mountpoints": ["/boot/efi"], "fstype": "vfat"},
         {"name": "nvme0n1p2", "mountpoints": ["/"], "fstype": "ext4"}]},
    {"name": "sdb", "path": "/dev/sdb", "size": 32e9, "model": "SanDisk Ultra", "vendor": "SanDisk", "tran": "usb",
     "rm": True, "type": "disk", "mountpoints": [None], "children": [
         {"name": "sdb1", "mountpoints": ["/media/dave/STICK"], "fstype": "vfat", "label": "STICK"}]},
    {"name": "sda", "path": "/dev/sda", "size": 2e12, "model": "WD Blue", "tran": "sata", "rm": False, "type": "disk",
     "mountpoints": ["/mnt/data"], "fstype": "ext4"},
    {"name": "sr0", "path": "/dev/sr0", "size": 0, "model": "DVD-RW", "tran": "sata", "rm": True, "type": "rom",
     "mountpoints": [None]},
    {"name": "loop0", "path": "/dev/loop0", "size": 1e6, "type": "loop"},
]}


def test_linux_listing_and_safety():
    ds = {d.id: d for d in parse_lsblk(LSBLK)}
    assert set(ds) == {"/dev/nvme0n1", "/dev/sdb", "/dev/sda", "/dev/sr0"}
    assert ds["/dev/nvme0n1"].system and not formattable(ds["/dev/nvme0n1"], allow_internal=True)[0]
    assert ds["/dev/sdb"].removable and formattable(ds["/dev/sdb"])[0]
    assert ds["/dev/sdb"].labels == ["STICK"] and ds["/dev/sdb"].mounts == ["/media/dave/STICK"]
    assert not formattable(ds["/dev/sda"])[0] and formattable(ds["/dev/sda"], allow_internal=True)[0]
    assert ds["/dev/sr0"].kind == "optical" and formattable(ds["/dev/sr0"])[0]


def test_confirmation_must_match_exactly():
    d = parse_lsblk(LSBLK)[1]
    with pytest.raises(ConversionError):
        check_confirm(d, "sdb")
    check_confirm(d, "/dev/sdb")


def test_plans_per_system():
    stick = parse_lsblk(LSBLK)[1]
    linux = plan_format(stick, "exfat", "My Stick!", False, "linux")
    assert ["umount", "/media/dave/STICK"] in linux and linux[-1] == ["mkfs.exfat", "-n", "My Stick", "/dev/sdb1"]
    assert any(c[0] == "dd" for c in plan_format(stick, "fat32", "x", True, "linux"))
    mac = Drive(id="disk4", name="USB", size=64 * 1024 ** 3, removable=True)
    assert plan_format(mac, "exfat", "USB", False, "darwin") == [["diskutil", "eraseDisk", "ExFAT", "USB", "MBR", "disk4"]]
    assert plan_format(mac, "fat32", "usb", True, "darwin")[0] == ["diskutil", "zeroDisk", "disk4"]
    with pytest.raises(ConversionError):
        plan_format(mac, "ext4", "x", False, "darwin")
    win = Drive(id="2", name="USB", size=64 * 1024 ** 3, removable=True)
    with pytest.raises(ConversionError, match="32 GB"):
        plan_format(win, "fat32", "x", False, "win32")
    assert plan_format(win, "exfat", "x", False, "win32")


def test_windows_parse_marks_system_disk():
    data = {"Disks": [{"Number": 0, "Name": "NVMe", "Size": 1e12, "Bus": "NVMe", "IsSystem": True, "Letters": ["C:"]},
                      {"Number": 2, "Name": "Kingston", "Size": 16e9, "Bus": "USB", "Letters": ["E:"], "Fs": ["FAT32"]}],
            "Optical": {"Drive": "D:", "Name": "DVD", "Loaded": False}}
    ds = parse_windows(data)
    assert ds[0].system and ds[1].removable and ds[2].kind == "optical" and ds[2].filesystems == ["no disc"]


def test_format_refuses_system_disk(monkeypatch):
    monkeypatch.setattr(drives, "list_drives", lambda: parse_lsblk(LSBLK))
    with pytest.raises(ConversionError, match="system"):
        drives.format_drive("/dev/nvme0n1", "exfat", "x", "/dev/nvme0n1", allow_internal=True)
    with pytest.raises(ConversionError, match="internal"):
        drives.format_drive("/dev/sda", "exfat", "x", "/dev/sda")
    with pytest.raises(ConversionError, match="Confirmation"):
        drives.format_drive("/dev/sdb", "exfat", "x", "wrong")
