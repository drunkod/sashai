{
  description = "SashAI Browser - A standalone flake for development";

  # В этом разделе мы объявляем все зависимости вашего проекта.
  # Основная зависимость - это репозиторий nixpkgs.
  inputs = {
    # Вы можете указать на официальный репозиторий nixpkgs.
    # Рекомендуется использовать конкретный коммит (rev) для полной воспроизводимости.
    # nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nixpkgs.url = "github:NixOS/nixpkgs/e643668fd71b949c53f8626614b21ff71a07379d";
    # ...или на ваш форк, если в нем есть необходимые изменения.
    # nixpkgs.url = "github:drunkod/nixpkgs/sashai-browser-1";
  };

  # В этом разделе мы определяем, что будет "создавать" наш flake:
  # пакеты, приложения, тесты и т.д.
  outputs = { self, nixpkgs }:
    let
      # Список систем, для которых будет собираться проект.
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];

      # Вспомогательная функция для генерации атрибутов для каждой системы.
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;

      # Создаем экземпляр nixpkgs для каждой поддерживаемой системы.
      pkgsFor = forAllSystems (system: import nixpkgs {
        inherit system;
        # Если вашему пакету нужны оверлеи или специальная конфигурация,
        # вы можете добавить ее здесь. Например:
        # config.allowUnfree = true;
      });
    in
    {
      # Определяем пакеты для каждой системы.
      packages = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
        in
        {
          # pkgs.callPackage автоматически передаст все необходимые зависимости
          # (stdenv, lib, fetchpatch и т.д.) из `pkgs` в ваш default.nix.
          default = pkgs.callPackage ./default.nix {
            # Здесь можно передать дополнительные аргументы, если они нужны.
            # В вашем случае, callPackage должен справиться автоматически.
          };
        });

      # Определяем приложения для запуска через `nix run`.
      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/chromium";
        };
      });

      # Пакет по умолчанию для команды `nix build`
      defaultPackage = self.packages.x86_64-linux.default;

      # Приложение по умолчанию для команды `nix run`
      defaultApp = self.apps.x86_64-linux.default;
    };
}

