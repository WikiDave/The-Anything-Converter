# Homebrew-formule voor de terminalversie van Anything Converter.
# Installeren:
#   brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
#   brew trust wikidave/anything-converter   (nieuwere Homebrew: taps van buiten moet je vertrouwen)
#   brew install anything-converter
# De release-workflow werkt versie en sha256 hieronder automatisch bij (desktop/update_formula.py).
class AnythingConverter < Formula
  desc "Converteer, verklein, vergroot en knip bestanden in je terminal"
  homepage "https://github.com/WikiDave/The-Anything-Converter"
  version "2.10.1"

  # Standaard: Linux (x86_64). Elke combinatie van systeem en processor moet een download hebben,
  # anders weigert nieuwere Homebrew de hele tap; Linux op ARM wordt daarom netjes geweigerd.
  url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.1/anything-converter-tui-linux-x64.tar.gz"
  sha256 "1549d857bed647bde196644e645fd5effd7b3b2016f6dfcf645fc8d4dee45a5b"

  on_macos do
    on_arm do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.1/anything-converter-tui-macos-arm64.tar.gz"
      sha256 "e114bffa988fdb1cea889c40935fd84388f4520a8fd709371c367c555419f129"
    end
    on_intel do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.1/anything-converter-tui-macos-x64.tar.gz"
      sha256 "0c529cdf265f4c7414573c99590f0ead345678a3d5f8456802440f6f9e5e67dd"
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
