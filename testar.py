import sys
 
from parser.grammar import gramatica
from parser.parser import criar_parser
from lexer.lexer import Lexer
from ast_nodes.builder import construir_ast
from semantico.semantico import analisar_semantica
from gerador_codigo.gerador import gerar_codigo
from gerador_codigo.instrucoes import formatar_programa
from maqhipo.maquina import MaquinaVirtual 
parser = criar_parser(gramatica)
 
TESTES = {}
 
 
def teste(nome, esperado, codigo):
    TESTES[nome] = (esperado, codigo)
 
 
teste("01 soma", "15\n", """package main
import "fmt"
func main() {
    x := 10
    y := 5
    fmt.Println(x + y)
}
""")
 
teste("02 if/else", "1\n", """package main
import "fmt"
func main() {
    x := 10
    if x > 5 {
        fmt.Println(1)
    } else {
        fmt.Println(0)
    }
}
""")
 
teste("03 for condicao", "0\n1\n2\n", """package main
import "fmt"
func main() {
    x := 0
    for x < 3 {
        fmt.Println(x)
        x++
    }
}
""")
 
teste("04 for completo + break/continue", "0\n1\n3\n4\n", """package main
import "fmt"
func main() {
    for i := 0; i < 10; i++ {
        if i == 2 {
            continue
        }
        if i == 5 {
            break
        }
        fmt.Println(i)
    }
}
""")
 
teste("05 funcao com retorno", "5\n", """package main
import "fmt"
func soma(a, b int) int {
    return a + b
}
func main() {
    fmt.Println(soma(2, 3))
}
""")
 
teste("06 recursao (fatorial)", "120\n", """package main
import "fmt"
func fat(n int) int {
    if n <= 1 {
        return 1
    }
    return n * fat(n-1)
}
func main() {
    fmt.Println(fat(5))
}
""")
 
teste("07 fibonacci recursivo", "55\n", """package main
import "fmt"
func fib(n int) int {
    if n < 2 {
        return n
    }
    return fib(n-1) + fib(n-2)
}
func main() {
    fmt.Println(fib(10))
}
""")
 
teste("08 retorno multiplo", "3 1\n", """package main
import "fmt"
func divmod(a, b int) (int, int) {
    return a / b, a % b
}
func main() {
    q, r := divmod(7, 2)
    fmt.Println(q, r)
}
""")
 
teste("09 globais e const", "42 100\n", """package main
import "fmt"
const base = 100
var g int = 42
func main() {
    fmt.Println(g, base)
}
""")
 
teste("10 float e conversoes", "7.5\n3\n2.5\n", """package main
import "fmt"
func main() {
    var f float64 = 2.5
    f = f * 3
    fmt.Println(f)
    n := int(f / 2.5)
    fmt.Println(n)
    fmt.Println(float64(5) / 2)
}
""")
 
teste("11 atribuicao composta, resto, bit a bit", "7\n1\n6\n8\n", """package main
import "fmt"
func main() {
    x := 5
    x += 2
    fmt.Println(x)
    fmt.Println(x % 2)
    fmt.Println(x ^ 1)
    fmt.Println(1 << 3)
}
""")
 
teste("12 troca a, b = b, a", "2 1\n", """package main
import "fmt"
func main() {
    a := 1
    b := 2
    a, b = b, a
    fmt.Println(a, b)
}
""")
 
teste("13 strings e bool", "ola mundo\ntrue\nfalse\n", """package main
import "fmt"
func main() {
    s := "ola" + " " + "mundo"
    fmt.Println(s)
    fmt.Println(3 > 2)
    fmt.Println(3 > 2 && 1 > 2)
}
""")
 
teste("14 else if", "b\n", """package main
import "fmt"
func main() {
    x := 5
    if x > 10 {
        fmt.Println("a")
    } else if x > 3 {
        fmt.Println("b")
    } else {
        fmt.Println("c")
    }
}
""")
 
teste("15 Printf e Sprintf", "x=7 y=2.50\nabc-9\n", """package main
import "fmt"
func main() {
    fmt.Printf("x=%d y=%.2f\\n", 7, 2.5)
    s := fmt.Sprintf("abc-%d", 9)
    fmt.Println(s)
}
""")
 
teste("16 curto-circuito || e &&", "chamou\nok\n", """package main
import "fmt"
func f() bool {
    fmt.Println("chamou")
    return true
}
func main() {
    if true || f() {
        fmt.Println("nao deveria chamar")
    }
    if false && f() {
        fmt.Println("nao")
    }
    if f() && true {
        fmt.Println("ok")
    }
}
""".replace('fmt.Println("nao deveria chamar")', 'x := 1\n        x++'))
 
teste("17 funcao sem retorno + chamada antes da definicao", "oi 3\n", """package main
import "fmt"
func main() {
    ola(3)
}
func ola(n int) {
    fmt.Println("oi", n)
}
""")
 
teste("18 for infinito com break + locais em bloco", "6\n", """package main
import "fmt"
func main() {
    total := 0
    i := 0
    for {
        i++
        if i > 3 {
            break
        }
        d := i
        total += d
    }
    fmt.Println(total)
}
""")
 
teste("19 global usada em funcao", "3\n", """package main
import "fmt"
var contador int
func inc() {
    contador++
}
func main() {
    inc()
    inc()
    inc()
    fmt.Println(contador)
}
""")
 
teste("20 if com inicializacao e rune", "10\n97\n", """package main
import "fmt"
func dobro(x int) int {
    return x * 2
}
func main() {
    if z := dobro(5); z > 5 {
        fmt.Println(z)
    }
    fmt.Println('a')
}
""")
 
 
teste("21 fmt.Print", "ab12\n", """package main
import "fmt"
func main() {
    fmt.Print("ab")
    fmt.Print(1)
    fmt.Print(2)
    fmt.Println()
}
""")
 
teste("22 unarios - ! ^", "-5\ntrue\n-6\n", """package main
import "fmt"
func main() {
    x := 5
    fmt.Println(-x)
    fmt.Println(!(x < 3))
    fmt.Println(^x)
}
""")
 
teste("23 bit a bit | & &^ >>", "7\n4\n1\n2\n", """package main
import "fmt"
func main() {
    fmt.Println(5 | 2)
    fmt.Println(5 & 6)
    fmt.Println(5 &^ 4)
    fmt.Println(8 >> 2)
}
""")
 
teste("24 compostas -= *= /= --", "7\n14\n7\n6\n", """package main
import "fmt"
func main() {
    x := 10
    x -= 3
    fmt.Println(x)
    x *= 2
    fmt.Println(x)
    x /= 2
    fmt.Println(x)
    x--
    fmt.Println(x)
}
""")
 
teste("25 strings: +=, ==, <", "ab\ntrue\ntrue\n", """package main
import "fmt"
func main() {
    s := "a"
    s += "b"
    fmt.Println(s)
    fmt.Println(s == "ab")
    fmt.Println("a" < "b")
}
""")
 
teste("26 var multiplo e tipado", "3 4\n", """package main
import "fmt"
func main() {
    var a, b int = 3, 4
    fmt.Println(a, b)
}
""")
 
teste("27 chamada aninhada", "9\n", """package main
import "fmt"
func dobro(x int) int {
    return x * 2
}
func main() {
    fmt.Println(dobro(dobro(2)) + 1)
}
""")
 
teste("28 Printf %s %t %c", "oi true A\n", """package main
import "fmt"
func main() {
    fmt.Printf("%s %t %c\\n", "oi", true, 65)
}
""")
 
teste("29 divisao e resto negativos", "-3\n-1\n", """package main
import "fmt"
func main() {
    fmt.Println(-7 / 2)
    fmt.Println(-7 % 2)
}
""")
 
teste("30 const tipada float", "6.28\n", """package main
import "fmt"
const pi float64 = 3.14
func main() {
    fmt.Println(pi * 2)
}
""")
 
selecionados = sys.argv[1:]
falhas = 0
 
for nome, (esperado, codigo) in TESTES.items():
    if selecionados and not any(nome.startswith(s) for s in selecionados):
        continue
 
    try:
        tokens, erros_lex = Lexer(codigo).analisar()
        if erros_lex:
            raise RuntimeError("léxico: " + "; ".join(map(str, erros_lex)))
 
        ast = construir_ast(parser.analisar(tokens))
 
        erros = analisar_semantica(ast)
        if erros:
            raise RuntimeError("semântico: " + "; ".join(map(str, erros)))
 
        instrucoes = gerar_codigo(ast)
        texto = formatar_programa(instrucoes, com_enderecos=True)
 
        saida = []
        vm = MaquinaVirtual(saida=saida.append)
        vm.carregar_texto(texto)
        vm.executar()
        obtido = "".join(saida)
 
        ok = obtido == esperado
        print(f"[{'OK' if ok else 'FALHOU'}] {nome}")
        if not ok:
            falhas += 1
            print("   esperado:", repr(esperado))
            print("   obtido:  ", repr(obtido))
            print(texto)
 
    except Exception as erro:
        falhas += 1
        print(f"[ERRO] {nome}: {type(erro).__name__}: {erro}")
 
print(f"\n{'TUDO OK' if not falhas else str(falhas) + ' falha(s)'}")
 