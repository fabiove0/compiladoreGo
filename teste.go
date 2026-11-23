package main

import "fmt"

func main() {
    // Declaração de variáveis
    var x int = 10
    var y int = 5
    var resultado int

    // Operações aritméticas
    resultado = x + y * 2

    fmt.Println("Resultado:", resultado)

    // Estrutura condicional
    if resultado > 15 {
        fmt.Println("O resultado é maior que 15")
    } else {
        fmt.Println("O resultado não é maior que 15")
    }

    // Estrutura de repetição
    for i := 0; i < 3; i++ {
        fmt.Println("Contagem:", i)
    }
}