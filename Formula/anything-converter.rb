# Homebrew-formule voor de terminalversie van Anything Converter.
# Installeren:
#   brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
#   brew trust wikidave/anything-converter   (nieuwere Homebrew: taps van buiten moet je vertrouwen)
#   brew install anything-converter
# De release-workflow werkt versie en sha256 hieronder automatisch bij (desktop/update_formula.py).
class AnythingConverter < Formula
  desc "Converteer, verklein, vergroot en knip bestanden in je terminal"
  homepage "https://github.com/WikiDave/The-Anything-Converter"
  version "2.10.2"

  # Standaard: Linux (x86_64). Elke combinatie van systeem en processor moet een download hebben,
  # anders weigert nieuwere Homebrew de hele tap; Linux op ARM wordt daarom netjes geweigerd.
  url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.2/anything-converter-tui-linux-x64.tar.gz"
  sha256 "7d604dde905b0e71198d6e0c62955563f147bb25483ad112597d245472de5b11"

  on_macos do
    on_arm do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.2/anything-converter-tui-macos-arm64.tar.gz"
      sha256 "0224d66870200bc7ff4cb457e1839ead52df1127959457dad65c38fb46d4ad37"
    end
    on_intel do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.2/anything-converter-tui-macos-x64.tar.gz"
      sha256 "b91cbeb2474fe15c4c7886bafc9ce9c4eca72cdc0dafd1f58aad2b0630c9e6e3"
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
