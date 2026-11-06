# Homebrew formula for the terminal version of Anything Converter.
# Install:
#   brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
#   brew trust wikidave/anything-converter   (newer Homebrew: outside taps must be trusted)
#   brew install anything-converter
# The release workflow updates the version and sha256 values below (desktop/update_formula.py).
class AnythingConverter < Formula
  desc "Convert, shrink, enlarge and trim almost any file in your terminal"
  homepage "https://github.com/WikiDave/The-Anything-Converter"
  version "2.10.2"

  # Default: Linux (x86_64). Every combination of system and processor has its own download
  # (newer Homebrew refuses a tap where one is missing): macOS Apple Silicon/Intel, Linux x86_64/ARM64.
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
    on_arm do
      url "https://github.com/WikiDave/The-Anything-Converter/releases/download/v2.10.1/anything-converter-tui-linux-arm64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  # Ready-made program (with its own Python, ffmpeg and yt-dlp): do not strip or change it.
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
      Start:  anything-converter-tui [file]
      Works in Terminal, iTerm, bash/zsh and over SSH. Quit with ctrl+q.
    EOS
  end

  test do
    assert_match "terminal", shell_output("#{bin}/anything-converter-tui --version")
  end
end
