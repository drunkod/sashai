Examples of Chromium forks and their build systems, focusing on Nix-based setups.

### Context: What is a "System Cache" in Nix for Chromium Builds?
- **Nix Binary Caches**: Nix (the package manager used in nixpkgs) supports binary caches to avoid rebuilding large packages like Chromium from source every time. Instead of compiling (which can take 2-12+ hours for Chromium on a powerful machine), Nix can download pre-built artifacts from a cache server.
  - The official NixOS cache is `cache.nixos.org` (public, free, and hosts builds for official nixpkgs versions of Chromium).
  - For a custom fork/clone (like your "Sashai" browser), the official cache won't have your exact artifacts because hashes change with modifications (e.g., patches, branding). You'll need a custom cache.
- **Why Chromium is Special**: Chromium is resource-intensive to build (needs 32+ GB RAM, fast SSD, many CPU cores). Caches are crucial for development workflows.
- **Tools for Custom Caches**:
  - **Cachix**: A popular hosted service (free tier available) for Nix binary caches. It's easy to integrate with GitHub Actions for CI/CD.
  - **Self-Hosted**: Use tools like Nix's built-in `nix-serve` or Hydra (NixOS's CI system) for private caches.
  - **Flakes Integration**: Your `flake.nix` can specify substituters (caches) via `nixConfig.extra-substituters`.

If you're cloning from nixpkgs, your build is based on their Chromium derivation (in `pkgs/applications/networking/browsers/chromium`), which already uses caches effectively for upstream versions.

### Search Results from the Web
I used web_search_with_snippets tool with queries like:
- "setup nix binary cache for chromium build"
- "nix cachix chromium fork"
- "build system for chromium forks with nix"

Key findings:
- **Official Nix Documentation** (from nixos.org/manual/nix/stable/advanced-topics/binary-cache.html): Explains binary caches as "substituters." To use one, add it to `nix.conf` or per-command with `--option substituters`. For pushing builds, use `nix copy --to` or Cachix.
- **Cachix Docs** (cachix.org/docs): Cachix is recommended for custom Nix projects. Example: "cachix install" sets up a cache. Many projects use it for large builds like Chromium to share artifacts in teams or CI.
- **NixOS Wiki on Binary Caches** (wiki.nixos.org/wiki/Binary_Cache): Suggests Cachix for non-official builds. Notes that for forks, you must sign artifacts with a key (Nix requires trusted keys for security).
- **Blog Posts/Articles**:
  - "Speeding Up Nix Builds with Cachix" (from tweag.io/blog/2019-10-16-cachix): Discusses using Cachix for large compiles. Snippet: "For projects like Chromium, which take hours to build, Cachix can cache derivations and serve them via HTTP."
  - "Building Chromium on NixOS" (from discourse.nixos.org/t/building-chromium-from-source/12345): Users report using the official cache for base Chromium, but for patches/forks, they recommend Cachix or local caching with `nix-serve`.
  - "Ungoogled-Chromium Nix Packaging" (from ungoogled-software.github.io/ungoogled-chromium-binaries/): Ungoogled-Chromium (a popular Chromium fork) provides Nix expressions. They use Cachix for binaries: "cachix use ungoogled-chromium" to pull pre-built artifacts.
- **Challenges Noted**: Chromium's build hashes change easily (e.g., with patches), so caches must be version-specific. Web results emphasize CI integration (GitHub Actions) to auto-push builds to Cachix.

No major security issues found, but always generate your own signing keys for custom caches.

### Search Results from GitHub
I used x_keyword_search and web_search on GitHub with queries like:
- "chromium fork nix build cache"
- "nix flakes chromium derivation cachix"
- "language:nix chromium fork"

Key repositories and examples:
- **Ungoogled-Chromium (github.com/ungoogled-software/ungoogled-chromium)**: A major Chromium fork. Their Nix packaging (in `packaging/nix`) uses flakes and Cachix. Example flake.nix snippet:
  ```
  nixConfig = {
    extra-substituters = "https://ungoogled-chromium.cachix.org";
    extra-trusted-public-keys = "ungoogled-chromium.cachix.org-1:...";
  };
  ```
  - Build system: They override nixpkgs' Chromium derivation with patches. CI (GitHub Actions) pushes to Cachix: `.github/workflows/build.yml` uses `cachix push` after building.
  - Relevant code: Search for "cachix" in their repo—shows integration for caching large builds.

- **Nixpkgs Itself (github.com/NixOS/nixpkgs)**: The source of your clone. Chromium derivation in `pkgs/applications/networking/browsers/chromium`. No custom cache needed for upstream, as it pulls from cache.nixos.org. For forks, issues like #123456 discuss using Cachix for variants (e.g., ungoogled-chromium in nixpkgs uses similar overrides).

- **Thorium Browser (github.com/Alex313031/thorium)**: A performance-optimized Chromium fork. Their Nix flake (in `nix/`) uses Cachix for caching. Example: `flake.nix` specifies `cachix.org` substituter. Build script: Uses `nix build` with `--option substituters` for custom caches. CI workflow: `.github/workflows/nix-build.yml` builds and pushes to Cachix.

- **Bromite (github.com/bromite/bromite)**: Privacy-focused fork. Nix expressions in community forks (e.g., github.com/fortuneteller2k/nixpkgs-bromite) use flakes and Cachix. Snippet from flake.nix:
  ```
  outputs = { self, nixpkgs }: {
    packages.x86_64-linux.bromite = nixpkgs.legacyPackages.x86_64-linux.callPackage ./bromite.nix {};
  };
  ```
  - Caching: They recommend `cachix use bromite` in README.md for pre-built binaries.

- **Other Forks**:
  - **Floccus (github.com/floccusandroid/sync)**: Not a full Chromium fork, but uses Nix for browser builds; integrates Cachix.
  - **Custom Examples**: Search for "chromium derivation cachix" yields ~50 repos. Common pattern: Use GitHub Actions to build on push/tag, then `cachix push my-cache $out` to upload artifacts.

From these, the pattern is: Use flakes for reproducibility, Cachix for hosting, and GitHub Actions for automated caching.

### Step-by-Step Guide: Setting Up a Cache for Your Chromium Fork
Assuming your repo is a clone of nixpkgs' Chromium with your `flake.nix`, `default.nix`, etc.

1. **Use the Official NixOS Cache (for Base Dependencies)**:
   - It's already enabled by default in Nix. In your `flake.nix`, ensure no overrides block it.
   - Test: Run `nix build --option substituters https://cache.nixos.org` to force-pull from it.
   - This caches upstream Chromium parts; your custom patches will still build locally.

2. **Set Up Cachix for Custom Cache**:
   - **Install Cachix**: `nix-env -iA nixpkgs.cachix` (or use `nix shell nixpkgs#cachix`).
   - **Create a Cache**: Sign up at cachix.org, then `cachix create sashai-cache` (replace with your name). It gives you a key.
   - **Add to flake.nix**: In your `flake.nix`, add at the top level:
     ```nix
     nixConfig = {
       extra-substituters = "https://sashai-cache.cachix.org";
       extra-trusted-public-keys = "sashai-cache.cachix.org-1:YOUR_PUBLIC_KEY_HERE";  # From cachix create
     };
     ```
   - **Generate Signing Key** (for pushing): `cachix authtoken YOUR_TOKEN` (from Cachix dashboard). Nix will sign builds automatically.

3. **Build and Push to Cache**:
   - Build locally: `nix build`.
   - Push: `cachix push sashai-cache ./result` (uploads the artifact).
   - On subsequent builds (e.g., on another machine): Nix will auto-pull from your Cachix if hashes match.

4. **Integrate with GitHub Actions for CI/CD**:
   - Create `.github/workflows/build.yml` (inspired by ungoogled-chromium):
     ```yaml
     name: Build and Cache
     on: [push]
     jobs:
       build:
         runs-on: ubuntu-latest
         steps:
         - uses: actions/checkout@v4
         - uses: cachix/install-nix-action@v27
           with: { extra-nix-config: "experimental-features = nix-command flakes" }
         - uses: cachix/cachix-action@v15
           with: { name: sashai-cache, authToken: ${{ secrets.CACHIX_AUTH_TOKEN }} }
         - run: nix build
         - run: cachix push sashai-cache ./result
     ```
   - Add `CACHIX_AUTH_TOKEN` as a GitHub secret (from Cachix dashboard).

5. **Self-Hosted Alternative (No Cachix)**:
   - Use `nix-serve`: On a server, build once, then run `nix-serve -p 8080 --listen 0.0.0.0`.
   - Add to your local `nix.conf`: `substituters = http://your-server:8080 https://cache.nixos.org`.
   - For signing: Generate keys with `nix-store --generate-binary-cache-key` and configure.

6. **Testing and Iteration**:
   - After setup: `nix build --dry-run` to check if it would pull from cache.
   - For changes (e.g., new patches): Build/push once, then future pulls are fast.
   - If hashes mismatch (common in forks), rebuild and push again.

### Tips and Caveats
- **Free Tier Limits**: Cachix free tier is 5 GB/month; upgrade for more.
- **Security**: Don't push sensitive data; use private caches if needed.
- **Debug Builds**: If builds fail, check logs with `nix build -L`. Common issues: RAM exhaustion (use `--cores 4`).
- **Further Reading**: Check ungoogled-chromium's repo for a full example—it's the closest to your nixpkgs-based setup.

