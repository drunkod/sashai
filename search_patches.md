Good question! Here's where to find information about patches needed for Chromium:

## 1. **NixOS/nixpkgs Official Chromium**
The best reference - see what nixpkgs maintainers use:

```bash
# Clone nixpkgs to see current patches
git clone --depth 1 https://github.com/NixOS/nixpkgs.git /tmp/nixpkgs
cd /tmp/nixpkgs

# Look at chromium directory
ls -la pkgs/applications/networking/browsers/chromium/

# See patches and common.nix
cat pkgs/applications/networking/browsers/chromium/common.nix | grep -A5 "patches ="
ls pkgs/applications/networking/browsers/chromium/patches/
```

**Online:** https://github.com/NixOS/nixpkgs/tree/master/pkgs/applications/networking/browsers/chromium

## 2. **Chromium Issue Tracker**
Search for build issues:
- https://issues.chromium.org/
- Search: `"Rust" "nixpkgs"` or `"compiler_builtins"`
- Example: https://issues.chromium.org/issues?q=compiler_builtins

## 3. **Chromium Code Review**
See what changes are being made:
- https://chromium-review.googlesource.com/
- Search for commits related to Rust/LLVM compatibility

## 4. **Arch Linux Chromium**
Arch often has similar system-library issues:
```bash
# View their PKGBUILD
curl https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/raw/main/PKGBUILD
```

## 5. **Gentoo Chromium**
Gentoo has detailed patches:
```bash
# Browse their patches
firefox https://gitweb.gentoo.org/repo/gentoo.git/tree/www-client/chromium
```

## 6. **For Your Specific Error**

Search in nixpkgs issues:
```bash
# GitHub issues search
firefox "https://github.com/NixOS/nixpkgs/issues?q=chromium+rust+compiler_builtins"
```

Search in Chromium's git history:
```bash
cd /tmp/nix-build-chromium-unwrapped-142.0.7444.0.drv-1/build/src
git log --all --grep="compiler_builtins" --oneline | head -20
git log --all --grep="rust.*alloc" --oneline | head -20
```

## 7. **Check Chromium Release Notes**
```bash
# For M142
firefox "https://chromiumdash.appspot.com/releases?platform=Linux"
firefox "https://chromium.googlesource.com/chromium/src/+log/142.0.7444.0"
```

## 8. **Compare with Working Version**

See what worked in M140/M141:
```bash
# In nixpkgs repo
git log --all -- pkgs/applications/networking/browsers/chromium/patches/chromium-140-rust.patch
git show <commit-hash>
```

## Practical Step NOW:

Let's check what the latest nixpkgs does:

```bash
curl -s "https://raw.githubusercontent.com/NixOS/nixpkgs/master/pkgs/applications/networking/browsers/chromium/common.nix" | grep -A30 "chromiumVersionAtLeast.*142\|chromiumVersionAtLeast.*140"
```

Or check the patches directory:
```bash
curl -s "https://api.github.com/repos/NixOS/nixpkgs/contents/pkgs/applications/networking/browsers/chromium/patches" | jq -r '.[].name' | grep -i rust
```

