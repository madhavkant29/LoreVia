param([string]$Root = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$story = Get-Content -LiteralPath (Join-Path $Root 'storyboard.json') -Raw | ConvertFrom-Json
$sentences = New-Object System.Collections.Generic.List[string]
foreach ($scene in $story.scenes) {
    foreach ($sentence in [regex]::Split($scene.narration, '(?<=[.!?])\s+')) {
        if ($sentence.Trim()) { $sentences.Add($sentence.Trim()) }
    }
}
$audioDir = Join-Path $Root 'audio\sentences'
New-Item -ItemType Directory -Path $audioDir -Force | Out-Null
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice.Rate = 2
    for ($i = 0; $i -lt $sentences.Count; $i++) {
        $path = Join-Path $audioDir ('{0:D3}.wav' -f $i)
        $voice.SetOutputToWaveFile($path)
        $voice.Speak($sentences[$i])
        $voice.SetOutputToNull()
    }
} finally {
    $voice.Dispose()
}
Write-Output "Recorded $($sentences.Count) narration sentences."
