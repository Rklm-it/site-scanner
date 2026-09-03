import SwiftUI
import AppKit

@main
struct VykladkaApp: App {

    @NSApplicationDelegateAdaptor(Delegat.self) var delegat
    @StateObject private var sostoyanie = Sostoyanie()

    var body: some Scene {
        WindowGroup("Выкладка") {
            GlavnoeOkno()
                .environmentObject(sostoyanie)
                .frame(minWidth: 940, minHeight: 620)
        }
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}

/// Ключ лежит в Связке, а ssh умеет читать его только из файла. Файл живёт
/// ровно столько, сколько открыто приложение, — при выходе убираем.
final class Delegat: NSObject, NSApplicationDelegate {
    func applicationWillTerminate(_ uvedomlenie: Notification) {
        Klyuchi.ubratFayl()
        Papki.pochistitVremennoe()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ prilozhenie: NSApplication) -> Bool {
        true
    }
}
