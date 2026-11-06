# Homebrew formula for the terminal version of Anything Converter.
# Install:
#   brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
#   brew trust wikidave/anything-converter   (newer Homebrew: outside taps must be trusted)
#   brew install anything-converter
# The release workflow updates the version and sha256 values below (desktop/update_formula.py).
class AnythingConverter < Formula
  desc "Convert, shrink, enlarge and trim almost any file in your terminal"
  homepage "https://github.com/WikiDave/The-Anything-Converter"
  version "2.10.1"

  # Default: Linux (x86_64). Every combination of system and processor has its own download
  # (newer Homebrew refuses a tap where one is missing): macOS Apple Silicon/Intel, Linux x86_64/ARM64.
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
