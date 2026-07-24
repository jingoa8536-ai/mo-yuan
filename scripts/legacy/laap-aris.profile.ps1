# ═══════════════════════════════════════════════════════════
#  Aris Digital Lifeform — PowerShell Profile Integration
#  加入此文件到你的 PowerShell profile 即可在 PS 中
#  直接输入 laap-aris 唤我。
#
#  加入方法:
#    notepad $PROFILE
#  然后在文件末尾加入:
#    . "D:\LAAP\laap-aris.profile.ps1"
# ═══════════════════════════════════════════════════════════

function laap-aris {
    param(
        [switch]$Status,
        [switch]$Memories,
        [switch]$NewWindow,
        [Parameter(Position=0, ValueFromRemainingArguments=$true)]
        [string[]]$Message
    )

    $ARIS_SCRIPT = "D:\LAAP\laap-aris.py"

    if (-not (Test-Path $ARIS_SCRIPT)) {
        Write-Error "Aris brain not found at $ARIS_SCRIPT"
        return
    }

    # Build args
    $argsList = @()
    if ($Status) { $argsList += "--status" }
    if ($Memories) { $argsList += "--memories" }
    if ($Message) { $argsList += $Message }

    if ($NewWindow) {
        $argStr = ($argsList -join " ")
        Start-Process cmd -ArgumentList "/c py -3 `"$ARIS_SCRIPT`" $argStr" -WindowStyle Normal
    } else {
        $argStr = ($argsList -join " ")
        & py -3 $ARIS_SCRIPT $argStr
    }
}

# 别名
Set-Alias -Name aris -Value laap-aris -Scope Global
