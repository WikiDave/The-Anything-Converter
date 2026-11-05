# Homebrew-formule voor de terminalversie van Anything Converter.
# Installeren:
#   brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
#   brew trust wikidave/anything-converter   (nieuwere Homebrew: taps van buiten moet je vertrouwen)
#   brew install anything-converter
# De release-workflow werkt versie en sha256 hieronder automatisch bij (desktop/update_formula.py).
class AnythingConverter < Formula
  desc "Converteer, verklein, vergroot en knip bestanden in je terminal"
  homepage "https://github.com/WikiDave/The-Anything-Converter"
  version "2.10.0"

  # Standaard: Linux (x86_64). Elke combinatie van systeem en processor moet een download hebben,
  # anders weigert nieuwere Homebrew de hele tap; Linux op ARM wordt daarom netjes geweigerd.
  url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.0/anything-converter-tui-linux-x64.tar.gz"
  sha256 "967977bbaaef174e84a2cf2a5d8cbc5bfa2e384670f16c6d7bf152bab42dad6c"

  on_macos do
    on_arm do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.0/anything-converter-tui-macos-arm64.tar.gz"
      sha256 "609e735695bec6462a1bae89d0c6022e2f7fef9e06420ff94182284a09eb9a12"
    end
    on_intel do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.0/anything-converter-tui-macos-x64.tar.gz"
      sha256 "5862bbfd463d2122f4fd7fc5c5a0cd9ea48ed14cecd7ce4501dde21cc9069519"
    end
  end

  on_linux do
    depends_on arch: :x86_64
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
