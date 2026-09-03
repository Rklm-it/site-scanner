import Foundation

/// Склонение существительного при числе: 1 заход, 2 захода, 5 заходов.
///
/// Без этого интерфейс пишет «1 заходов с 1 адресов» — мелочь, которая сразу
/// выдаёт, что текст собран программой и никто его не читал.
func sklonenie(_ chislo: Int, _ odin: String, _ dva: String, _ pyat: String) -> String {
    let sotni = abs(chislo) % 100
    if sotni >= 11 && sotni <= 14 { return pyat }
    switch abs(chislo) % 10 {
    case 1: return odin
    case 2...4: return dva
    default: return pyat
    }
}

/// Число вместе со словом: «83 дня», «1 заход».
func schislom(_ chislo: Int, _ odin: String, _ dva: String, _ pyat: String) -> String {
    "\(chislo) \(sklonenie(chislo, odin, dva, pyat))"
}
