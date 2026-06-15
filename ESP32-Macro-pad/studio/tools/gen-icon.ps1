# Generates the Macropad Studio app icon: a dark rounded tile with the 12-key
# RGB grid in the real hardware layout. Renders a 512px master, downscales to
# the standard icon sizes, and writes a 32px tray image. Run with Windows
# PowerShell (System.Drawing): powershell -ExecutionPolicy Bypass -File gen-icon.ps1
# Then `node tools/make-icon.js` packs the PNGs into assets/icon.ico.

Add-Type -AssemblyName System.Drawing

$AssetDir = Join-Path $PSScriptRoot '..\assets'
New-Item -ItemType Directory -Force -Path $AssetDir | Out-Null

# 12-colour palette around the wheel — evokes the WS2812 RGB LEDs.
$palette = @(
  '#ff3b5c','#ff7a3d','#ffd23d','#8cff3d','#3dff7a','#3dffd2',
  '#3dd2ff','#3d7aff','#7a3dff','#d23dff','#ff3dd2','#ff3d7a'
)

function HexColor([string]$hex, [int]$a = 255) {
  $r = [Convert]::ToInt32($hex.Substring(1,2),16)
  $g = [Convert]::ToInt32($hex.Substring(3,2),16)
  $b = [Convert]::ToInt32($hex.Substring(5,2),16)
  return [System.Drawing.Color]::FromArgb($a,$r,$g,$b)
}

function RoundRectPath($x,$y,$w,$h,$r) {
  $d = 2*$r
  $p = New-Object System.Drawing.Drawing2D.GraphicsPath
  $p.AddArc($x,$y,$d,$d,180,90)
  $p.AddArc($x+$w-$d,$y,$d,$d,270,90)
  $p.AddArc($x+$w-$d,$y+$h-$d,$d,$d,0,90)
  $p.AddArc($x,$y+$h-$d,$d,$d,90,90)
  $p.CloseFigure()
  return $p
}

# Render the master at S px.
$S = 512
$bmp = New-Object System.Drawing.Bitmap $S, $S
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$g.Clear([System.Drawing.Color]::Transparent)

# Background rounded tile with a subtle vertical gradient.
$pad = [int]($S*0.055)
$bw = $S - 2*$pad
$bgPath = RoundRectPath $pad $pad $bw $bw ([int]($S*0.20))
$bgRect = New-Object System.Drawing.Rectangle $pad, $pad, $bw, $bw
$bgBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($bgRect, (HexColor '#1a1a24'), (HexColor '#0a0a10'), 90)
$g.FillPath($bgBrush, $bgPath)
# thin border
$borderPen = New-Object System.Drawing.Pen((HexColor '#2b2b3a' 200), [single]([int]($S*0.006)))
$g.DrawPath($borderPen, $bgPath)

# 4x4 grid, corners empty -> the 12-key layout:  . K K . / K K K K / K K K K / . K K .
$gridInset = [int]($S*0.14)
$gridX = $gridInset
$gridW = $S - 2*$gridInset
$cell = $gridW / 4.0
$side = $cell * 0.74
$ofs = ($cell - $side) / 2.0

$active = @(
  @(0,1),@(0,2),
  @(1,0),@(1,1),@(1,2),@(1,3),
  @(2,0),@(2,1),@(2,2),@(2,3),
  @(3,1),@(3,2)
)

for ($i = 0; $i -lt $active.Count; $i++) {
  $r = $active[$i][0]; $c = $active[$i][1]
  $kx = $gridX + $c*$cell + $ofs
  $ky = $gridX + $r*$cell + $ofs
  $col = HexColor $palette[$i]

  # soft glow: two expanded low-alpha passes behind the key.
  foreach ($gl in @(@(10,46),@(5,80))) {
    $exp = $gl[0]; $al = $gl[1]
    $gp = RoundRectPath ($kx-$exp) ($ky-$exp) ($side+2*$exp) ($side+2*$exp) ($side*0.30)
    $gb = New-Object System.Drawing.SolidBrush((HexColor $palette[$i] $al))
    $g.FillPath($gb, $gp); $gb.Dispose(); $gp.Dispose()
  }
  # key cap
  $kp = RoundRectPath $kx $ky $side $side ($side*0.26)
  $kb = New-Object System.Drawing.SolidBrush($col)
  $g.FillPath($kb, $kp); $kb.Dispose()
  # top highlight for a glossy cap
  $hp = RoundRectPath ($kx+$side*0.16) ($ky+$side*0.12) ($side*0.68) ($side*0.34) ($side*0.16)
  $hb = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(70,255,255,255))
  $g.FillPath($hb, $hp); $hb.Dispose(); $hp.Dispose(); $kp.Dispose()
}
$g.Dispose()

# Save master + downscaled sizes + tray.
$master = Join-Path $AssetDir 'icon.png'
$bmp.Save($master, [System.Drawing.Imaging.ImageFormat]::Png)

foreach ($sz in 256,128,64,48,32,16) {
  $out = New-Object System.Drawing.Bitmap $sz, $sz
  $og = [System.Drawing.Graphics]::FromImage($out)
  $og.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $og.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $og.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $og.Clear([System.Drawing.Color]::Transparent)
  $og.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0,0,$sz,$sz))
  $og.Dispose()
  $out.Save((Join-Path $AssetDir "icon-$sz.png"), [System.Drawing.Imaging.ImageFormat]::Png)
  if ($sz -eq 32) { $out.Save((Join-Path $AssetDir 'tray.png'), [System.Drawing.Imaging.ImageFormat]::Png) }
  $out.Dispose()
}
$bmp.Dispose()
Write-Output "icon PNGs written to $AssetDir"
