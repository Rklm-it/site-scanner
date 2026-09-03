// swift-tools-version: 5.9
//
// «Выкладка» — приложение для macOS: положил архив с собранным сайтом, он
// уехал на VPS, домен прописался в Caddy, и дальше видно, кто на сайт заходил.
//
// Сторонних зависимостей здесь нет намеренно. Всё, что нужно для SSH, уже есть
// в macOS: /usr/bin/ssh, ssh-keygen, tar. Приложение ими и пользуется — значит
// ведёт себя ровно как хозяин в терминале, не тащит в проект реализацию SSH и
// не ломается при обновлении чужой библиотеки.

import PackageDescription

let package = Package(
    name: "Vykladka",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Vykladka",
            path: "Sources/Vykladka"
        )
    ]
)
