# Homebrew-formule voor de terminalversie van Anything Converter.
# Installeren:
#   brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
#   brew trust wikidave/anything-converter   (nieuwere Homebrew: taps van buiten moet je vertrouwen)
#   brew install anything-converter
# De release-workflow werkt versie en sha256 hieronder automatisch bij (desktop/update_formula.py).
class AnythingConverter < Formula
  desc "Converteer, verklein, vergroot en knip bestanden in je terminal"
  homepage "https://github.com/WikiDave/The-Anything-Converter"
  version "2.9.0"

  # Standaard: Linux (x86_64). Elke combinatie van systeem en processor moet een download hebben,
  # anders weigert nieuwere Homebrew de hele tap; Linux op ARM wordt daarom netjes geweigerd.
  url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.9.0/anything-converter-tui-linux-x64.tar.gz"
  sha256 "00cd03343663ba17298331cc9a4ec66275635fb8f5b891b677df0e31378bfacc"

  on_macos do
    on_arm do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.9.0/anything-converter-tui-macos-arm64.tar.gz"
      sha256 "39998cefd53861702fdde864c1f1681261774250d8aaa8d0df24e9ae63a4544b"
    end
    on_intel do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.9.0/anything-converter-tui-macos-x64.tar.gz"
      sha256 "3b87f76480968ce4f4f2c1d1e973d9568cbbb9f012d4009e0267b4961139a85c"
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
