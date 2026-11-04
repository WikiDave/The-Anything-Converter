# Homebrew-formule voor de terminalversie van Anything Converter.
# Installeren:
#   brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
#   brew install anything-converter
# De release-workflow werkt versie en sha256 hieronder automatisch bij (desktop/update_formula.py).
class AnythingConverter < Formula
  desc "Converteer, verklein, vergroot en knip bestanden in je terminal"
  homepage "https://github.com/WikiDave/The-Anything-Converter"
  version "2.6.0"

  on_macos do
    on_arm do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.6.0/anything-converter-tui-macos-arm64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
    on_intel do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.6.0/anything-converter-tui-macos-x64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.6.0/anything-converter-tui-linux-x64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  # Kant-en-klaar programma (met eigen Python, ffmpeg en yt-dlp): niet strippen of aanpassen.
  skip_clean "libexec"

  def install
    if OS.mac?
      (libexec/"AnythingConverter.app").install Dir["*"]
      bin.install_symlink libexec/"AnythingConverter.app/Contents/MacOS/anything-converter-tui"
    else
      libexec.install Dir["*"]
      bin.install_symlink libexec/"anything-converter-tui"
    end
  end

  def caveats
    <<~EOS
      Starten:  anything-converter-tui [bestand]
      Werkt in Terminal, iTerm, bash/zsh en via SSH. Afsluiten met ctrl+q.
    EOS
  end

  test do
    assert_match "terminal", shell_output("#{bin}/anything-converter-tui --version")
  end
end
