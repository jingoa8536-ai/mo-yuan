<#
.SYNOPSIS
    LAAP V5 — Digital Lifeform CLI (PowerShell launcher)
.DESCRIPTION
    Makes "laap" command available globally in PowerShell.
    Launches Hermes Agent + LAAP V5 AGI full stack.
.EXAMPLE
    laap status
    laap --version
    laap setup
#>
$LaapCmd = "python"
$LaapArgs = @("D:\LAAP\laap\cli\laap_main.py") + $args
& $LaapCmd $LaapArgs
