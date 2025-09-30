{
  description = "SashAI Browser - A standalone flake for development";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/e643668fd71b949c53f8626614b21ff71a07379d";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = forAllSystems (system: import nixpkgs {
        inherit system;
      });
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
        in
        {
          default = pkgs.callPackage ./default.nix { };
        });
 #test
      apps = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
        in
        {
          default = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/chromium";
          };
          update-chromium = {
            type = "app";
            program = "${pkgs.writeShellScriptBin "update-chromium" ''
              #!/usr/bin/env bash
              export PATH=${pkgs.git}/bin:$PATH
              ${pkgs.zx}/bin/zx ${self}/update.mjs --chromium
            ''}/bin/update-chromium";
          };
        });

      defaultPackage = self.packages.x86_64-linux.default;
      defaultApp = self.apps.x86_64-linux.default;
    };
}

