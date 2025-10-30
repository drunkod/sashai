
# Tutorial: Finding and Creating Patches for Chromium Builds

A comprehensive guide to finding patches when building Chromium from source.

## Table of Contents

1. [Understanding Patches](#understanding-patches)
2. [Primary Patch Sources](#primary-patch-sources)
3. [Search Strategies](#search-strategies)
4. [Using Chromium Gerrit](#using-chromium-gerrit)
5. [Analyzing Build Errors](#analyzing-build-errors)
6. [Creating Your Own Patches](#creating-your-own-patches)
7. [Real-World Example](#real-world-example)
8. [Quick Reference](#quick-reference)

---

## Understanding Patches

### What Are Patches?

Patches are small modifications to Chromium's source code that fix compatibility issues with:
- System libraries (vs bundled versions)
- Different compiler versions
- Different toolchains (Clang, GCC, Rust)
- Distribution-specific configurations

### When Do You Need Patches?

- Build errors that don't occur in official Chromium builds
- Symbol mismatches between system and bundled libraries
- Compiler/linker errors specific to your toolchain
- Missing features in system libraries

---

## Primary Patch Sources

### 1. **Linux Distribution Repositories**

#### Arch Linux (Most Current)
```bash
# Browse online
https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/tree/main

# Download PKGBUILD and patches
git clone https://gitlab.archlinux.org/archlinux/packaging/packages/chromium.git
cd chromium
ls *.patch
```

**Why Arch?** 
- Rolling release = latest patches
- Quick to adapt to new Chromium versions
- Well-documented PKGBUILD

#### Gentoo
```bash
https://gitweb.gentoo.org/repo/gentoo.git/tree/www-client/chromium
```

**Why Gentoo?**
- Source-based distribution
- Extensive patching for different configurations
- Good for cross-compilation issues

#### Fedora
```bash
https://src.fedoraproject.org/rpms/chromium/tree/rawhide
```

#### Debian/Ubuntu
```bash
https://salsa.debian.org/chromium-team/chromium/-/tree/master/debian/patches
```

### 2. **NixOS/nixpkgs**

```bash
# Current patches
https://github.com/NixOS/nixpkgs/tree/master/pkgs/applications/networking/browsers/chromium/patches

# Commit history
https://github.com/NixOS/nixpkgs/commits/master/pkgs/applications/networking/browsers/chromium

# Clone and search locally
git clone https://github.com/NixOS/nixpkgs.git
cd nixpkgs/pkgs/applications/networking/browsers/chromium
git log --oneline patches/
```

### 3. **Ungoogled Chromium**

```bash
https://github.com/ungoogled-software/ungoogled-chromium/tree/master/patches

# Useful for privacy/Google service removal patches
```

### 4. **Chromium Code Review (Gerrit)**

Main source for upstream fixes:
```bash
https://chromium-review.googlesource.com/
```

### 5. **Chromium Issue Tracker**

```bash
https://issues.chromium.org/
```

---

## Search Strategies

### Step 1: Identify the Error

Extract key information from your build error:
- **File path**: `build/rust/allocator/lib.rs`
- **Symbol name**: `__rust_alloc_error_handler_should_panic`
- **Error type**: `undefined symbol`, `undefined reference`, `missing library`
- **Component**: `Rust`, `LLVM`, `compiler-rt`, etc.

### Step 2: Search Distribution Patches First

```bash
# Search Arch Linux patches
curl -s https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/raw/main/PKGBUILD | grep "\.patch"

# Download and examine a patch
curl -O https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/raw/main/compiler-rt-adjust-paths.patch
cat compiler-rt-adjust-paths.patch
```

### Step 3: Search by Error Message

Google with site filters:
```
"__rust_alloc_error_handler_should_panic" site:chromium-review.googlesource.com
"undefined symbol" rust allocator site:issues.chromium.org
```

### Step 4: Search Chromium Git History

In your failed build directory:
```bash
cd /tmp/nix-build-chromium-*/build/src

# Search commit messages
git log --all --grep="rust allocator" --oneline

# Search for symbol additions/removals
git log --all -S"__rust_alloc_error_handler_should_panic" --oneline

# Show actual changes
git log --all -p -S"__rust_alloc_error_handler_should_panic" -- build/rust/allocator/lib.rs

# Search by file
git log --all --oneline -- build/rust/allocator/lib.rs
```

---

## Using Chromium Gerrit

### Basic Search Syntax

Access: https://chromium-review.googlesource.com/

### Common Search Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `file:` | `file:build/rust/allocator/lib.rs` | Search by file path |
| `message:` | `message:"alloc_error_handler"` | Search commit messages |
| `status:` | `status:merged` | Filter by change status |
| `after:` | `after:2024-11-01` | Changes after date |
| `before:` | `before:2024-12-31` | Changes before date |
| `owner:` | `owner:hans@chromium.org` | By author |
| `project:` | `project:chromium/src` | By project |
| `branch:` | `branch:main` | By branch |

### Practical Gerrit Searches

**1. Find changes to a specific file:**
```
https://chromium-review.googlesource.com/q/file:build/rust/allocator/lib.rs+status:merged
```

**2. Search by error message:**
```
https://chromium-review.googlesource.com/q/message:"__rust_alloc_error_handler_should_panic"
```

**3. Recent Rust changes:**
```
https://chromium-review.googlesource.com/q/project:chromium/src+file:^build/rust/.*+after:2024-10-01+status:merged
```

**4. Changes between versions:**
```
https://chromium-review.googlesource.com/q/file:build/rust/allocator/lib.rs+after:2024-08-01+before:2024-10-01
```

**5. Complex search:**
```
https://chromium-review.googlesource.com/q/(message:compiler-rt+OR+file:build/config/clang/)+status:merged
```

### Reading Gerrit Results

Click on a change to see:
1. **Commit message** - Explains WHY the change was made
2. **Files tab** - Shows WHAT was changed
3. **Diff view** - Line-by-line changes
4. **Bug references** - Links to issues (Bug: 440481922)

---

## Analyzing Build Errors

### Common Error Patterns

#### 1. Undefined Symbol

```
ld.lld: error: undefined symbol: __rust_alloc_error_handler_should_panic
```

**What to do:**
1. Identify the symbol name
2. Search Gerrit for recent changes: `message:"symbol_name"`
3. Check if symbol was renamed/removed
4. Look for `_v2` versions or similar

#### 2. Missing Library

```
error: '../../../../nix/store/.../libclang_rt.builtins-x86_64.a', missing and no known rule to make it
```

**What to do:**
1. Note the expected path
2. Search for similar issues: `"libclang_rt.builtins" site:archlinux.org`
3. Check compiler-rt related patches
4. Look for path adjustment patches

#### 3. Rust Version Mismatch

```
error: the option `Z` is only accepted on the nightly compiler
```

**What to do:**
1. Search for Rust nightly feature flags
2. Look for `RUSTC_BOOTSTRAP` environment variable
3. Check distribution build scripts

#### 4. API Changes

```
error: no method named 'foo' found for type 'Bar'
```

**What to do:**
1. Identify the library (e.g., pipewire, wayland)
2. Search for version-specific patches
3. Check library changelog
4. Look for backport patches

---

## Creating Your Own Patches

### Step 1: Find the Original Code

Use Gerrit's file viewer:
```bash
# View current version
https://chromium.googlesource.com/chromium/src/+/refs/tags/142.0.7444.0/build/rust/allocator/lib.rs

# View previous version
https://chromium.googlesource.com/chromium/src/+/refs/tags/141.0.7390.0/build/rust/allocator/lib.rs
```

Or download directly:
```bash
# Current version
curl -s "https://chromium.googlesource.com/chromium/src/+/refs/tags/142.0.7444.0/build/rust/allocator/lib.rs?format=TEXT" | base64 -d > current.rs

# Previous version
curl -s "https://chromium.googlesource.com/chromium/src/+/refs/tags/141.0.7390.0/build/rust/allocator/lib.rs?format=TEXT" | base64 -d > previous.rs

# Compare
diff -u previous.rs current.rs
```

### Step 2: Create the Patch File

**Method 1: Manual Creation**
```bash
cat > patches/chromium-142-rust-allocator-compat.patch << 'EOF'
diff --git a/build/rust/allocator/lib.rs b/build/rust/allocator/lib.rs
index b92aec8..restored 100644
--- a/build/rust/allocator/lib.rs
+++ b/build/rust/allocator/lib.rs
@@ -97,6 +97,13 @@ mod both_allocators {
     }
 
     // Mangle the symbol name as rustc expects.
+    // Re-added for compatibility with older Rust stdlibs
+    #[rustc_std_internal_symbol]
+    #[allow(non_upper_case_globals)]
+    #[linkage = "weak"]
+    static __rust_alloc_error_handler_should_panic: u8 = 0;
+
+    // Mangle the symbol name as rustc expects.
     #[rustc_std_internal_symbol]
     #[allow(non_upper_case_globals)]
     #[linkage = "weak"]
EOF
```

**Method 2: From Git (if you have a checkout)**
```bash
cd /tmp/chromium-source
git diff > ~/my-patch.patch
```

**Method 3: Using patch command**
```bash
# In the source tree
cp build/rust/allocator/lib.rs build/rust/allocator/lib.rs.orig
# Make your changes to lib.rs
diff -u build/rust/allocator/lib.rs.orig build/rust/allocator/lib.rs > patches/my-fix.patch
```

### Step 3: Test the Patch

```bash
# Test if patch applies cleanly
cd /tmp/nix-build-chromium-*/build/src
patch -p1 --dry-run < /path/to/your.patch

# Apply for real
patch -p1 < /path/to/your.patch

# Revert if needed
patch -R -p1 < /path/to/your.patch
```

### Step 4: Add to Nix Build

In `common.nix`:
```nix
patches = [
  # ... existing patches ...
  ./patches/chromium-142-rust-allocator-compat.patch
]
```

Or with conditions:
```nix
++ lib.optionals (chromiumVersionAtLeast "142") [
  ./patches/chromium-142-rust-allocator-compat.patch
]
```

---

## Real-World Example

### Problem: Undefined Symbol Error

**Error:**
```
ld.lld: error: undefined symbol: __rustc::__rust_alloc_error_handler_should_panic
```

### Investigation Process

**Step 1: Search Gerrit**
```
https://chromium-review.googlesource.com/q/message:"__rust_alloc_error_handler_should_panic"
```

**Found:**
- Aug 22: Added `_v2` version
- Sep 10: Removed old version

**Step 2: View the Changes**

Click on the Sep 10 commit:
```
https://chromium-review.googlesource.com/c/chromium/src/+/6935385/2/build/rust/allocator/lib.rs
```

See what was removed:
```rust
#[rustc_std_internal_symbol]
#[allow(non_upper_case_globals)]
#[linkage = "weak"]
static __rust_alloc_error_handler_should_panic: u8 = 0;
```

**Step 3: Understand Why**

Commit message says:
> Current Rust (rolled in crrev.com/1513010) uses the _v2 function

**Step 4: Create Patch**

Revert the removal for compatibility with older Rust:
```patch
diff --git a/build/rust/allocator/lib.rs b/build/rust/allocator/lib.rs
index b92aec8..restored 100644
--- a/build/rust/allocator/lib.rs
+++ b/build/rust/allocator/lib.rs
@@ -97,6 +97,13 @@ mod both_allocators {
     }
 
+    // Re-added for nixpkgs compatibility
+    #[rustc_std_internal_symbol]
+    #[allow(non_upper_case_globals)]
+    #[linkage = "weak"]
+    static __rust_alloc_error_handler_should_panic: u8 = 0;
+
     #[rustc_std_internal_symbol]
     #[allow(non_upper_case_globals)]
     #[linkage = "weak"]
```

---

## Quick Reference

### Fast Commands

```bash
# Find patches in Arch
curl -s https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/raw/main/PKGBUILD | grep -o '[^ ]*\.patch'

# Download Arch patch
curl -O https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/raw/main/PATCH_NAME.patch

# Search Chromium git for symbol
cd /tmp/nix-build-chromium-*/build/src
git log --all -S"SYMBOL_NAME" --oneline

# View file at specific version
curl -s "https://chromium.googlesource.com/chromium/src/+/refs/tags/VERSION/path/to/file?format=TEXT" | base64 -d

# Compare two versions
diff <(curl -s "URL_OLD?format=TEXT" | base64 -d) <(curl -s "URL_NEW?format=TEXT" | base64 -d)
```

### Useful Links

- **Gerrit**: https://chromium-review.googlesource.com/
- **Issues**: https://issues.chromium.org/
- **Source Browser**: https://source.chromium.org/
- **Git Web**: https://chromium.googlesource.com/chromium/src/
- **Arch Chromium**: https://gitlab.archlinux.org/archlinux/packaging/packages/chromium
- **Gentoo Chromium**: https://gitweb.gentoo.org/repo/gentoo.git/tree/www-client/chromium
- **NixOS Chromium**: https://github.com/NixOS/nixpkgs/tree/master/pkgs/applications/networking/browsers/chromium

### Patch File Structure

```patch
diff --git a/path/to/file b/path/to/file
index old_hash..new_hash mode
--- a/path/to/file
+++ b/path/to/file
@@ -line,count +line,count @@ context
-removed line
+added line
 unchanged line
```

### Common Patch Patterns

**1. Adding compatibility symbols:**
```patch
+    #[no_mangle]
+    pub extern "C" fn compat_function() {
+        // ...
+    }
```

**2. Path adjustments:**
```patch
-        _dir = "x86_64-unknown-linux-gnu"
+        _dir = "linux"
```

**3. Version checks:**
```patch
-    assert.equal(expected, actual);
+    assert.ok(expected <= actual);
```

---

## Tips and Tricks

### 1. Always Check Multiple Sources

Don't rely on just one distribution—compare:
- Arch (latest)
- Gentoo (comprehensive)
- NixOS (similar toolchain)
- Upstream Gerrit (official fixes)

### 2. Understand the Root Cause

Before applying a patch:
- Read the commit message
- Understand WHY it was needed
- Check if it applies to your situation

### 3. Test Patches Incrementally

```bash
# Test one patch at a time
patch -p1 --dry-run < patch1.patch
# If successful
patch -p1 < patch1.patch
# Then test build
```

### 4. Document Your Patches

Add comments in your patch files:
```patch
# Fix Rust allocator compatibility with nixpkgs
# Reverts https://chromium-review.googlesource.com/c/chromium/src/+/6935385
# for compatibility with Rust < 1.XX
diff --git a/...
```

### 5. Keep Patches Minimal

- Only change what's necessary
- Don't combine multiple fixes in one patch
- Make patches version-specific when possible

### 6. Version-Specific Patches

In Nix:
```nix
++ lib.optionals (chromiumVersionAtLeast "142") [
  ./patches/chromium-142-specific.patch
]
++ lib.optionals (chromiumVersionAtLeast "140" && !chromiumVersionAtLeast "142") [
  ./patches/chromium-140-141.patch
]
```

---

## Troubleshooting Patch Application

### Patch Doesn't Apply

```bash
# Check line numbers (might have offset)
patch -p1 --verbose < your.patch

# See what would change
patch -p1 --dry-run --verbose < your.patch

# Force with fuzz
patch -p1 --fuzz=3 < your.patch
```

### Wrong Directory Level

```bash
# Try different -p levels
patch -p0 < your.patch  # No path stripping
patch -p1 < your.patch  # Remove a/ b/ prefix (most common)
patch -p2 < your.patch  # Remove two levels
```

### Reverse Patch

```bash
# If patch is already applied
patch -R -p1 < your.patch
```

---

## Contributing Patches Upstream

If you create a useful patch:

1. **Test thoroughly**
2. **Check if it's already reported**: https://issues.chromium.org/
3. **Create an issue** describing the problem
4. **Submit to distributions** (Arch AUR, nixpkgs PR)
5. **Consider submitting to Chromium** (via Gerrit if it's a real bug)

---

## Conclusion

Finding patches for Chromium is a skill that improves with practice:

1. **Start with distributions** - They've likely solved your problem
2. **Search Gerrit** - Find official upstream solutions  
3. **Understand the changes** - Don't blindly apply patches
4. **Test incrementally** - One patch at a time
5. **Document everything** - Help the next person

Remember: Most Chromium build issues have been solved before. The key is knowing where to look!

---

**Last Updated:** Based on Chromium M142 (Jan 2025)  
**Maintainer:** Your tutorial, feel free to update!
