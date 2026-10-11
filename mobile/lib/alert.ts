import { Alert, AlertButton, Platform } from "react-native";

/**
 * Alert.alert is a no-op on react-native-web, so fall back to the browser's
 * dialogs there. Supports the common shapes: a notice, or cancel + one action.
 */
export function showAlert(title: string, message?: string, buttons?: AlertButton[]) {
  if (Platform.OS !== "web") {
    Alert.alert(title, message, buttons);
    return;
  }
  const text = message ? `${title}\n\n${message}` : title;
  const action = buttons?.find((b) => b.style !== "cancel" && b.onPress);
  if (buttons && buttons.length > 1 && action) {
    if (window.confirm(text)) action.onPress?.();
  } else {
    window.alert(text);
    buttons?.[0]?.onPress?.();
  }
}
