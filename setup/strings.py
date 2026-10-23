"""VPNGo Setup's words, in Brazilian Portuguese and English, picked from the system language."""

import locale
import os

TEXT = {
    "pt-BR": {
        "window": "Instalar o VPNGo",
        "install_title": "Instalar o VPNGo",
        "upgrade_title": "Atualizar o VPNGo",
        "install_body": "Cada app na sua rota. Escolha como você quer usar:",
        "gui": "Aplicativo VPNGo",
        "gui_detail": "A janela e o ícone na bandeja, com o comando vpngo. Baixa cerca de 250 MB.",
        "cli": "Só o comando vpngo",
        "cli_detail": "Para usar no terminal, sem a interface.",
        "proxifyre": "Instalar também o roteamento do Windows (ProxiFyre)",
        "proxifyre_detail": "Necessário para os apps passarem pela VPN. Pede permissão de administrador.",
        "license": "Licença Apache 2.0",
        "cancel": "Cancelar",
        "install": "Instalar",
        "upgrade": "Atualizar",
        "progress_title": "Instalando o VPNGo",
        "progress_body": "Na primeira vez leva alguns minutos.",
        "step_python": "Preparar o Python",
        "step_download": "Baixar o vpngo",
        "step_files": "Copiar os arquivos",
        "step_command": "Criar o comando vpngo",
        "step_gui": "Instalar a interface",
        "step_proxifyre": "Instalar o ProxiFyre",
        "step_finish": "Concluir",
        "details_show": "Mostrar detalhes",
        "details_hide": "Esconder detalhes",
        "done_title": "Pronto.",
        "done_gui": "O VPNGo está instalado e aparece no menu Iniciar.",
        "done_cli": "O vpngo está instalado. Abra um terminal novo e rode vpngo version.",
        "open": "Abrir o VPNGo",
        "close": "Fechar",
        "partial_title": "Quase lá.",
        "failed_title": "Não deu certo.",
        "retry": "Tentar de novo",
        "uninstall_title": "Desinstalar o VPNGo?",
        "uninstall_body": "Remove o vpngo e a interface. Seus perfis, configurações e histórico ficam guardados.",
        "uninstall": "Desinstalar",
        "uninstalling_title": "Desinstalando o VPNGo",
        "uninstalled_title": "Desinstalado.",
        "uninstalled_body": "O VPNGo foi removido. Seus perfis e configurações continuam guardados.",
    },
    "en": {
        "window": "Install VPNGo",
        "install_title": "Install VPNGo",
        "upgrade_title": "Update VPNGo",
        "install_body": "Every app on its own route. Choose how you want to use it:",
        "gui": "VPNGo app",
        "gui_detail": "The window and the tray icon, with the vpngo command. Downloads about 250 MB.",
        "cli": "Only the vpngo command",
        "cli_detail": "For the terminal, without the interface.",
        "proxifyre": "Also install Windows routing (ProxiFyre)",
        "proxifyre_detail": "Needed for apps to go through the VPN. Asks for administrator permission.",
        "license": "Apache License 2.0",
        "cancel": "Cancel",
        "install": "Install",
        "upgrade": "Update",
        "progress_title": "Installing VPNGo",
        "progress_body": "The first time takes a few minutes.",
        "step_python": "Prepare Python",
        "step_download": "Download vpngo",
        "step_files": "Copy the files",
        "step_command": "Create the vpngo command",
        "step_gui": "Install the interface",
        "step_proxifyre": "Install ProxiFyre",
        "step_finish": "Finish",
        "details_show": "Show details",
        "details_hide": "Hide details",
        "done_title": "Done.",
        "done_gui": "VPNGo is installed and in the Start menu.",
        "done_cli": "vpngo is installed. Open a new terminal and run vpngo version.",
        "open": "Open VPNGo",
        "close": "Close",
        "partial_title": "Almost there.",
        "failed_title": "That didn't work.",
        "retry": "Try again",
        "uninstall_title": "Uninstall VPNGo?",
        "uninstall_body": "Removes vpngo and the interface. Your profiles, settings and history are kept.",
        "uninstall": "Uninstall",
        "uninstalling_title": "Uninstalling VPNGo",
        "uninstalled_title": "Uninstalled.",
        "uninstalled_body": "VPNGo was removed. Your profiles and settings are still kept.",
    },
}


def language():
    if os.environ.get("VPNGO_LANG"):
        return "pt-BR" if os.environ["VPNGO_LANG"].lower().startswith("pt") else "en"
    if os.name == "nt":
        import ctypes
        try:
            # The Windows display language, which the locale module does not report.
            return "pt-BR" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x16 else "en"
        except (AttributeError, OSError):
            pass
    return "pt-BR" if (locale.getlocale()[0] or "").lower().startswith("pt") else "en"


LANGUAGE = language()


def tr(key):
    return TEXT[LANGUAGE][key]
