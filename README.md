# Compilador de um Subconjunto de Go (análise ascendente SLR(1))

**Aluno:** Fabio Ventura Lima  
**Curso / Disciplina:** Ciência da Computação - Projeto de Compiladores

Compilador escrito em Python, sem bibliotecas de geração de analisadores (lex, yacc, etc.).
Ele traduz um subconjunto da linguagem **Go** para o código de uma **máquina hipotética de pilha (MaqHipo)** e inclui a **máquina virtual** que executa esse código.

```
programa.go ──► COMPILADOR ──► programa.obj ──► MÁQUINA VIRTUAL ──► saída
   (Parte 1)                                        (Parte 2)
```

**Sumário**
1. [Objetivo](#1-objetivo)
2. [Escopo da linguagem: o que foi implementado e o que ficou de fora](#2-escopo-da-linguagem)
3. [A gramática adotada](#3-a-gramática-adotada)
4. [Estrutura do projeto](#4-estrutura-do-projeto)
5. [O fluxo de compilação, etapa por etapa](#5-o-fluxo-de-compilação-etapa-por-etapa)
6. [A máquina virtual (MaqHipo)](#6-a-máquina-virtual-maqhipo)
7. [Como executar](#7-como-executar)
8. [Testes realizados](#8-testes-realizados)
9. [Limitações conhecidas](#9-limitações-conhecidas)
10. [Uso de Inteligência Artificial](#10-uso-de-inteligência-artificial)

---

## 1. Objetivo

Implementar um compilador para a linguagem **Go**, usando a técnica de **análise sintática ascendente** (método **SLR(1)**, algoritmo *shift-reduce*), cobrindo todas as fases:

| Fase | O que faz |
|---|---|
| Análise léxica | transforma o texto em *tokens* |
| Análise sintática (SLR(1)) | confere se os tokens formam um programa válido |
| Construção da AST | monta uma árvore enxuta do programa |
| Análise semântica | confere nomes, tipos, escopos e regras de Go |
| Geração de código | traduz a AST para instruções da MaqHipo e grava o `.obj` |
| Máquina virtual | lê o `.obj` e executa as instruções |

Como o Go oficial é muito grande, foi definida uma **gramática simplificada** (seção 3). O compilador **não** pretende aceitar qualquer programa Go.

---

## 2. Escopo da linguagem

### 2.1 O que foi implementado

| Categoria | Recursos aceitos |
|---|---|
| Estrutura | `package`, `import "fmt"` (com apelido opcional), declarações globais |
| Tipos | `int`, `float64`, `string`, `bool`, `rune` |
| Variáveis | `var x int`, `var x = 5`, `var a, b int = 1, 2`, declaração curta `x := 10`, `a, b := 1, 2` |
| Constantes | `const pi = 3.14`, `const n int = 10` (aceitam só expressões constantes) |
| Operadores aritméticos | `+ - * / %` |
| Operadores de bits | `& \| ^ &^ << >>` e o unário `^x` |
| Comparação e lógica | `== != < <= > >=`, `&& \|\| !` (com curto-circuito) |
| Atribuição | `=` e as compostas `+= -= *= /= %= &= \|= ^= <<= >>= &^=`; atribuição múltipla (`a, b = b, a`) |
| Incremento | `x++`, `x--` |
| Condicional | `if`, `else`, `else if`, com inicialização (`if z := f(); z > 5 {}`) |
| Repetição | `for {}`, `for cond {}`, `for i := 0; i < n; i++ {}`, com `break` e `continue` |
| Funções | parâmetros, retorno único ou **múltiplo**, recursão, chamada antes da definição |
| Conversões | `int(x)`, `float64(x)`, `string(x)`, `rune(x)`, `bool(x)` |
| Saída | `fmt.Println`, `fmt.Print`, `fmt.Printf`, `fmt.Sprintf` |
| Literais | inteiros (`10`, `0xFF`, `0b101`, `0o17`, `0755`, `1_000`), reais (`3.14`, `.5`, `1e6`), strings, runes (`'a'`) |
| Comentários | `//` e `/* */` |

### 2.2 O que ficou de fora

| Recurso do Go oficial | Situação |
|---|---|
| `struct`, `type`, métodos, interfaces | não aceito (erro sintático) |
| `switch`, `select`, `goto`, `defer`, `go`, `range` | não aceito (erro sintático) |
| `map`, `chan`, operador `<-` | não aceito |
| Arrays, slices, ponteiros | não existem (`v[i]` passa no parser, mas o semântico rejeita) |
| `import (...)`, `var (...)`, `const (...)` com parênteses | não aceito |
| Pacotes além de `fmt` | rejeitado pelo semântico |
| Entrada de dados (`fmt.Scan` etc.) | **não suportado** pela linguagem |
| Funções anônimas, closures, generics | não aceito |
| `f(g())` quando `g` devolve vários valores | rejeitado (use `a, b := g(); f(a, b)`) |

> O lexer **reconhece** as palavras `switch`, `struct`, `map` etc. como tokens, mas a gramática não as usa. Assim, o erro aparece no parser com uma mensagem clara.

---

## 3. A gramática adotada

A gramática está em `parser/grammar.py`, escrita como um dicionário Python: **nome da regra → lista de alternativas**.

| Dado | Valor |
|---|---|
| Não terminais | 44 |
| Terminais | 60 |
| Produções | 125 |
| Estados do autômato LR(0) | 206 |
| Conflitos na tabela SLR(1) | **0** |

> Os números de não terminais, terminais e produções foram conferidos contra o `grammar.py` atual. Estados (206), transições (1115) e entradas das tabelas (seção 5.2) vêm da última execução de `python3 -m parser.parsing_table`;

### 3.1 Forma geral de um programa

```
Programa  ->  package IDENT ;   (import ...)*   (declaração global ;)*
declaração global  ->  var ...  |  const ...  |  func ...
```

Um programa **começa** com `package` e, para ser executável, precisa ter `func main()` sem parâmetros e sem retorno (essa última regra é conferida na análise semântica).

### 3.2 Expressões e precedência

A precedência dos operadores de Go (5 faixas) está embutida na gramática, da menor para a maior:

```
Expr
 └─ ExprOu          ||
     └─ ExprE        &&
         └─ ExprComparacao   == != < <= > >=
             └─ ExprSoma     + - | ^
                 └─ ExprProduto    * / % << >> & &^
                     └─ ExprUnaria    + - ! ^
                         └─ ExprPrimaria   chamadas, a.b, v[i]
                             └─ Operando   nome, número, texto, (expr)
```

Por isso `a + b * c` já sai da análise sintática como `a + (b * c)`.

### 3.3 Ajustes para a gramática ser SLR(1)

Para a tabela não ter conflitos, a gramática aceita **um pouco mais** do que o Go aceita, e a análise seguinte rejeita o excesso:

| Ajuste na gramática | Quem rejeita o excesso |
|---|---|
| Lado esquerdo de `:=` é uma lista de expressões (não só nomes) | semântico: "só nomes de variáveis" |
| Condição de `if`/`for` chega como "comando simples" | construtor da AST: "a condição deve ser uma expressão" |
| Comando só de expressão aceita qualquer expressão | semântico: "só chamadas de função" |
| `ForInicio` e `ForPasso` são regras separadas (iguais) | evita conflito logo após a palavra `for` |
| `Bloco` tem uma alternativa sem o último `;` | permite `{ x++ }` como em Go |

### 3.4 Exemplos

**Aceito:**

```go
package main

import "fmt"

func soma(a, b int) int {
    return a + b
}

func main() {
    x := 10
    for i := 0; i < 3; i++ {
        x = soma(x, i)
    }
    fmt.Println("x =", x)
}
```

**Rejeitado, com a fase que barra e a mensagem do compilador** (a lista de "Esperado" no erro sintático depende do estado do parser):

| Programa | Fase | Mensagem |
|---|---|---|
| `type Pessoa struct {...}` | Sintático | `token 'type' inesperado. Esperado: $, const, func, import, var.` |
| `switch x { }` | Sintático | `token 'switch' inesperado. Esperado: ...` |
| `x := 5 @ 2` | Léxico | `Caractere inválido. Caractere: '@'` |
| `if x := 5 { }` | AST | `A condição do if deve ser uma expressão.` |
| `var n int = "oi"` | Semântico | `não é possível usar string como int em declaração` |
| `x := 5` (e `x` nunca usado) | Semântico | `variável 'x' declarada e não usada` |
| `fmt.Println(v[0])` | Semântico | `indexação com [] ainda não é suportada (a linguagem não tem arrays)` |
| `import "os"` | Semântico | `pacote 'os' não é suportado (disponível: fmt)` |
| programa sem `func main()` | Semântico | `função 'main' não foi declarada` |

---

## 4. Estrutura do projeto

```
Compilador/
├── lexer/               análise léxica
│   ├── lexer.py         o analisador léxico
│   ├── token.py         classe Token (tipo, lexema, linha, coluna)
│   └── errors.py        classe ErroLexico
│
├── parser/              análise sintática SLR(1)
│   ├── grammar.py       a gramática + validação + ligação com o lexer
│   ├── first_follow.py  cálculo dos conjuntos FIRST e FOLLOW
│   ├── lr0.py           autômato LR(0): closure, goto, estados
│   ├── parsing_table.py tabelas ACTION e GOTO (detecta conflitos)
│   └── parser.py        algoritmo shift-reduce + árvore de derivação
│
├── ast_nodes/           árvore sintática abstrata
│   ├── nodes.py         classes dos nós da AST (tem um autoteste em __main__)
│   └── builder.py       converte a árvore do parser na AST
│
├── semantico/           análise semântica
│   ├── semantico.py     visitante que confere e anota a AST
│   └── simbolos.py      tabela de símbolos e regras de tipos
│
├── gerador_codigo/      geração de código objeto
│   ├── gerador.py       visitante que percorre a AST e emite instruções
│   └── instrucoes.py    classe Instrucao + gravação do .obj
│
├── maqhipo/             máquina virtual
│   └── maquina.py       lê o .obj e executa
│
├── exemplos/            programas Go de exemplo
├── testar.py            roda os 30 programas de teste (seção 8)
├── teste.go             programa de exemplo
├── programa.obj         código objeto gerado
├── main.py              ponto de entrada: compila e executa (seção 7)
└── README.md
```
---

## 5. O fluxo de compilação, etapa por etapa

```
 código Go
    │
    ▼
┌──────────┐  tokens   ┌───────────────┐  árvore de   ┌─────────────┐
│  LEXER   ├──────────►│ PARSER SLR(1) ├─────────────►│ BUILDER AST │
└──────────┘           └───────────────┘  derivação   └──────┬──────┘
                                                             │ AST
                       ┌───────────────┐   AST anotada  ┌────▼────────┐
         programa.obj◄─┤   GERADOR     │◄───────────────┤  SEMÂNTICO  │
                       └───────────────┘  (tipos, ...)  └─────────────┘
```

Cada etapa só roda se a anterior não encontrou erros. É exatamente essa sequência que o `main.py` executa. Nas seções abaixo, usamos este programa como exemplo (`exemplos/exemplo.go`):

```go
package main

import "fmt"

func soma(a, b int) int {
    return a + b
}

func main() {
    x := 10
    for i := 0; i < 3; i++ {
        x = soma(x, i)
    }
    fmt.Println("x =", x)
}
```

### 5.1 Análise léxica (`lexer/`)

O lexer lê o texto caractere a caractere e agrupa os caracteres em **tokens**. Cada token guarda `tipo`, `lexema`, `linha` e `coluna`.

Para `x := 10`:

```
Token(tipo=IDENTIFICADOR,          lexema='x',  linha=1, coluna=1)
Token(tipo=DECLARACAO_ATRIBUICAO,  lexema=':=', linha=1, coluna=3)
Token(tipo=NUMERO_INTEIRO,         lexema='10', linha=1, coluna=6)
Token(tipo=PONTO_VIRGULA,          lexema=';',  linha=1, coluna=8)   ← inserido automaticamente
```

O que o lexer reconhece:

| Elemento | Detalhe |
|---|---|
| Palavras reservadas | as 25 de Go (`if`, `for`, `func`, ...) |
| Identificadores | letras, dígitos e `_` |
| Números | decimais, hexadecimais (`0x`), binários (`0b`), octais (`0o`), reais, expoente (`1e6`), separador `_` |
| Strings e runes | com escapes (strings: `\a \b \f \n \r \t \v \\ \"`; runes: os mesmos com `\'` no lugar de `\"`, mais octal de 3 dígitos como `'\000'`) |
| Operadores e delimitadores | os de Go usados pela linguagem (mais `<-`, `...`, `~`, `:`), escolhendo sempre o mais longo (`<<=` antes de `<<` antes de `<`) |
| Comentários | `//` e `/* */` (ignorados) |
| `;` automático | no fim da linha, como Go faz, quando o último token é um nome, número, texto, rune, `break`, `continue`, `fallthrough`, `return`, `)`, `]`, `}`, `++` ou `--`; também no fim do arquivo e depois de comentário de bloco que contém quebra de linha |

Erros léxicos detectados (com linha e coluna): caractere inválido, string não fechada, escape inválido, rune inválido, comentário de bloco não fechado, número malformado (base ou dígitos inválidos, expoente sem dígitos, `_` fora do lugar). **Todos os erros são coletados**, sem parar no primeiro.

### 5.2 Análise sintática SLR(1) (`parser/`)

É a parte central do trabalho. O parser **não** usa nenhuma biblioteca: as tabelas são **construídas automaticamente a partir da gramática**, em quatro passos, cada um em um arquivo.

```
grammar.py ─► first_follow.py ─► lr0.py ─► parsing_table.py ─► parser.py
 gramática      FIRST/FOLLOW     estados     ACTION / GOTO      shift-reduce
```

**Passo 1: FIRST e FOLLOW (`first_follow.py`)**

- **FIRST(X)**: conjunto de terminais que podem **começar** uma derivação de X. Exemplo calculado: `FIRST(Expr) = { !, (, +, -, ^, IDENTIFICADOR, NUMERO_INTEIRO, NUMERO_REAL, RUNE, STRING }`.
- **FOLLOW(A)**: conjunto de terminais que podem aparecer **logo depois** de A. Serve para decidir *quando é seguro reduzir*.
- O cálculo repete as regras até **nenhum conjunto crescer mais** (ponto fixo). O FOLLOW do símbolo inicial contém `$` (fim da entrada).

**Passo 2: Autômato LR(0) (`lr0.py`)**

- Um **item** é uma produção com um ponto marcando até onde já foi reconhecida: `A -> X · Y Z`. No código, é a tupla `(não_terminal, alternativa, posição_do_ponto)`.
- `closure`: se o ponto está antes de um não terminal, adiciona as produções dele com o ponto no início.
- `goto`: avança o ponto sobre um símbolo e calcula o fechamento do novo estado.
- A gramática é **aumentada** com `Programa' -> Programa`, para o parser saber quando aceitar.
- Resultado para esta gramática: **206 estados** e **1115 transições**.

**Passo 3: Tabelas ACTION e GOTO (`parsing_table.py`)**

| Tabela | Chave | Valor |
|---|---|---|
| ACTION | (estado, terminal) | `SHIFT estado`, `REDUCE produção` ou `ACCEPT` |
| GOTO | (estado, não terminal) | próximo estado após uma redução |

Como a tabela é preenchida:

- transição por **terminal** → `SHIFT`;
- transição por **não terminal** → `GOTO`;
- item completo `A -> α ·` → `REDUCE` em cada terminal de **FOLLOW(A)** (é isso que torna o método *SLR*);
- `Programa' -> Programa ·` → `ACCEPT` no `$`.

Se duas ações disputarem a mesma célula, o programa registra o **conflito** (*shift/reduce* ou *reduce/reduce*) e recusa-se a rodar. Para esta gramática: **0 conflitos** (ACTION com 2397 entradas, GOTO com 425).

**Passo 4: Algoritmo shift-reduce (`parser.py`)**

O parser mantém duas pilhas em paralelo: **estados** e **nós da árvore**. A cada passo, consulta `ACTION[estado do topo, próximo token]`:

```
SHIFT n   → empilha o token e o estado n; avança na entrada
REDUCE p  → desempilha |lado direito de p| itens, cria um nó para o lado esquerdo,
            consulta GOTO e empilha o novo estado
ACCEPT    → fim; o nó que sobrou na pilha é a raiz da árvore
(sem ação)→ erro sintático
```

Em caso de erro, a mensagem traz **linha, coluna, o token encontrado e a lista de tokens esperados**:

```
Erro sintático na linha 2, coluna 1: token 'type' inesperado. Esperado: $, const, func, import, var.
```

Se o erro for no fim do arquivo, a mensagem diz "fim do arquivo" em vez de um token.

A saída é a **árvore de derivação**: um nó para cada regra usada (inclusive a cadeia de precedência das expressões). Ela é grande demais para as próximas etapas, e por isso existe a AST.

### 5.3 AST (`ast_nodes/`)

**Ideia:** a árvore do parser guarda todos os detalhes da gramática (`;`, `,`, `Expr → ExprOu → ExprE → ...`). A **AST** guarda só o que importa para significado e geração de código:

```
x = x + 2 * y        vira        Atribuicao(=)
                                  ├─ alvo:  Identificador x
                                  └─ valor: Binaria +
                                             ├─ Identificador x
                                             └─ Binaria *
                                                ├─ LiteralInteiro 2
                                                └─ Identificador y
```

- `nodes.py`: uma classe por construção. Programa, Import, DeclVar, DeclConst, Tipo, DeclFuncao, Parametro, Bloco, DeclaracaoCurta, Atribuicao, IncDec, Return, Break, Continue, If, For, ComandoExpressao, Identificador, LiteralInteiro, LiteralReal, LiteralString, LiteralRune, Unaria, Binaria, Chamada, AcessoMembro, Indexacao.
- Todo nó tem **linha e coluna** (para as mensagens de erro) e o método `aceitar(visitante)` (padrão *Visitor*): o semântico e o gerador são classes separadas, com um método `visitar_<Nó>` por nó.
- Toda **expressão** tem o campo `tipo`, que começa vazio e é preenchido pelo semântico.
- `builder.py` faz três simplificações: (1) listas recursivas viram listas Python; (2) cadeias de precedência são colapsadas (só viram `Binaria`/`Unaria` quando há operador); (3) literais viram valores reais (`0x1F` → `31`, `0755` → `493`, `"a\n"` → texto com quebra de linha, `'a'` → `97`).
- Um grupo de parâmetros como `a, b int` é expandido em **um nó `Parametro` por nome**.
- Erros do builder (`ErroAST`) cobrem o que a gramática aceita a mais e não cabe na AST (condição de `if`/`for` que não é expressão, lista de expressões usada como comando, literal inválido).

### 5.4 Análise semântica (`semantico/`)

O parser garante a **forma**; o semântico garante o **sentido**. É um visitante que percorre a AST e, ao mesmo tempo:

1. **confere** as regras e junta os erros numa lista, ordenada por linha e coluna (mostra todos de uma vez);
2. **anota** a AST para o gerador: cada expressão ganha `tipo`, cada identificador ganha `simbolo`, cada chamada ganha `tipos`, `eh_conversao` e `builtin`; cada `var`/`const` ganha seus `simbolos`; cada `:=` ganha `novos` (quais variáveis foram criadas).

A **tabela de símbolos** (`simbolos.py`) é uma pilha de escopos: `universo` (tipos, `true`, `false`) → `pacote` (imports, funções, globais) → blocos (parâmetros, locais). A busca vai do escopo mais interno para fora, por isso uma variável local "esconde" uma global. O corpo da função e seus parâmetros dividem o mesmo escopo, e o escopo de um `if` cobre inicialização, condição e todos os `else`.

A análise é feita em passos: (1) imports; (2) assinaturas de **todas** as funções, para uma função poder chamar outra declarada depois; (3) variáveis e constantes globais, na ordem do arquivo; (4) corpo das funções; (5) conferência de `main` e de imports não usados.

**Verificações implementadas:**

| Área | Regras |
|---|---|
| Nomes | declarado antes de usar; sem redeclaração no mesmo escopo; `_` não pode ser lido |
| Tipos | operações, atribuições, argumentos e retornos com tipos compatíveis; `int` + `float64` é erro, como em Go |
| Constantes sem tipo | `2` serve como `int` ou `float64` conforme o contexto (`var f float64 = 2` vale) |
| `:=` | precisa de ao menos uma variável nova; só aceita nomes |
| Condições | `if` e `for` exigem `bool` |
| Funções | número e tipo de argumentos; quantidade de valores de retorno; função com retorno precisa terminar em `return` (ou `if/else` com `return` nos dois lados, ou `for` sem condição e sem `break`) |
| Controle | `break`/`continue` só dentro de `for` |
| Uso | variável local não usada e import não usado são **erros** (como em Go) |
| Constantes | só expressões constantes; não se pode atribuir a uma `const` |
| `main` | precisa existir, sem parâmetros e sem retorno |
| `fmt` | `Println`, `Print`, `Printf`, `Sprintf` |
| Divisão | divisão ou resto **inteiro** por zero literal é erro |

**Simplificações em relação ao Go:** uma constante real só vira `float64` (em Go, `var i int = 2.0` vale; aqui dá erro); não se confere *overflow* de constantes; só literais são conferidos em `int(2.5)`.

Exemplo da AST **depois** do semântico (tipos entre colchetes):

```
Programa (pacote main)
  declaracao: DeclFuncao main
    corpo: Bloco
      comando: DeclaracaoCurta
        alvo: Identificador x [int]
        valor: LiteralInteiro 10 [int]
      comando: For
        inicializacao: DeclaracaoCurta ...
        condicao: Binaria < [bool]
          esquerda: Identificador i [int]
          direita: LiteralInteiro 3 [int]
        passo: IncDec ++
        corpo: Bloco
          comando: Atribuicao =
            alvo: Identificador x [int]
            valor: Chamada [int]
              funcao: Identificador soma
              ...
```

### 5.5 Geração de código (`gerador_codigo/`)

O gerador percorre a AST anotada (visitante) e acrescenta instruções a uma lista (o "array C" da máquina). No fim, `instrucoes.py` valida cada instrução e grava a lista em `programa.obj`, **uma instrução por linha**.

**Três ideias resumem o gerador:**

1. **Toda expressão deixa seu valor no topo da pilha.** Então `a + b` é: gera `a`, gera `b`, emite `SOMA`.
2. **Desvios usam correção de endereço.** Emite-se `DSVF ?` e, quando se descobre onde o bloco termina, o `?` é preenchido. O mesmo vale para chamadas de função (a função pode estar mais abaixo no arquivo). Se sobrar algum `?`, a gravação do `.obj` acusa erro.
3. **Variáveis têm endereços.** Globais usam `CRVL`/`ARMZ` (endereço fixo). Locais e parâmetros usam `CRVF`/`ARMF` (endereço relativo à base `b` da função).

**Estrutura do programa gerado:**

```
INPP                  inicia a máquina
ALME <n>              reserva as n variáveis globais
...                   inicialização das globais
CHPR <main>           chama main
PARA                  fim
...                   o código de cada função
```

**Como cada construção é traduzida:**

| Go | Código gerado |
|---|---|
| `a + b` | `CRVF a` · `CRVF b` · `SOMA` |
| `x = expr` | *(expr)* · `ARMF x` |
| `x += expr` | `CRVF x` · *(expr)* · *(operador)* · `ARMF x` |
| `x++` / `x--` | `CRVF x` · `CRCT 1` · `SOMA` / `SUBT` · `ARMF x` |
| `a, b = b, a` | *(b)* · *(a)* · `ARMF b` · `ARMF a` (todos os valores são calculados antes de guardar) |
| `var x int` (sem valor) | `CRCT 0` (ou `0.0` para `float64`, `""` para `string`) · `ARMF x` |
| `if c { A } else { B }` | *(c)* · `DSVF else` · *A* · `DSVI fim` · *B* |
| `for c { corpo }` | `início:` *(c)* · `DSVF fim` · *corpo* · `DSVI início` |
| `a && b` | *(a)* · `DSVF falso` · *(b)* · `DSVI fim` · `falso: CRCT 0` |
| `a \|\| b` | *(a)* · `NEGA` · `DSVF verdadeiro` · *(b)* · `DSVI fim` · `verdadeiro: CRCT 1` |
| `f(x)` | `ALME r` (retornos) · *(x)* · `CHPR f` |
| chamada usada como comando | a chamada · `DESM n` (descarta os `n` valores devolvidos) |
| `return v` | *(v)* · `ARMF k-r` para cada um dos `r` valores, do último para o primeiro (com `r = 1`, `ARMF -1`) · `RTPR n` |
| `break` / `continue` | `DSVI` para o fim do laço / para o passo do laço |
| `int(x)`, `float64(x)`... | *(x)* · `CONV tipo` |

`&&` e `||` usam **desvios** (curto-circuito, como em Go): o lado direito só é calculado se necessário.

**Funções (protocolo com a máquina):**

```
Quem chama:  ALME r         espaço para os r valores de retorno
             (argumentos)   empilha os argumentos
             CHPR end       chama a função
A função:    ENPR n         n = nº de parâmetros
             ALME m         espaço para as variáveis locais
             ...
             RTPR n         volta ao chamador

Frame, a partir da base b:
   b-r .. b-1    valores de retorno
   b .. b+n-1    parâmetros
   b+n, b+n+1    endereço de retorno e b antigo (guardados pela máquina)
   b+n+2 ..      variáveis locais
```

**Impressão (`fmt`):**

| Chamada | Código gerado |
|---|---|
| `Println(a, b)` | cada valor com `IMPR` (ou `IMPB` se for `bool`), um espaço (`CRCT " "` · `IMPR`) entre eles, e `QUEB` no fim |
| `Print(a, b)` | cada valor com `IMPR`/`IMPB`, sem espaço e sem quebra |
| `Printf(f, ...)` | formato e valores empilhados · `FMT n` · `IMPR` |
| `Sprintf(f, ...)` | formato e valores empilhados · `FMT n` (o texto fica na pilha como valor da expressão) |

**Código objeto do exemplo** (os `#` com o endereço são comentários opcionais; a VM os ignora):

```
INPP              # 0     início
ALME 0            # 1     0 globais
CHPR 12           # 2     chama main (começa no endereço 12)
PARA              # 3     fim
ENPR 2            # 4     ── func soma(a, b)
ALME 0            # 5
CRVF 0            # 6     a
CRVF 1            # 7     b
SOMA              # 8
ARMF -1           # 9     guarda o valor de retorno
RTPR 2            # 10
RTPR 2            # 11
ENPR 0            # 12    ── func main
ALME 2            # 13    locais: x e i
CRCT 10           # 14
ARMF 2            # 15    x := 10
CRCT 0            # 16
ARMF 3            # 17    i := 0
CRVF 3            # 18    ◄── início do for
CRCT 3            # 19
CPME              # 20    i < 3
DSVF 32           # 21    falso: sai do laço
ALME 1            # 22    espaço do retorno de soma
CRVF 2            # 23    x
CRVF 3            # 24    i
CHPR 4            # 25    soma(x, i)
ARMF 2            # 26    x = resultado
CRVF 3            # 27
CRCT 1            # 28
SOMA              # 29
ARMF 3            # 30    i++
DSVI 18           # 31    volta ao início do for
CRCT "x ="        # 32    ◄── fim do for
IMPR              # 33
CRCT " "          # 34
IMPR              # 35
CRVF 2            # 36
IMPR              # 37    Println("x =", x)
QUEB              # 38
RTPR 0            # 39
```

Saída ao executar: `x = 13`

---

## 6. A máquina virtual (MaqHipo)

`maqhipo/maquina.py` lê o `.obj` e executa as instruções. A máquina é de **pilha**:

| Elemento | Papel |
|---|---|
| `C` | área de código: lista de instruções (endereço = posição, a partir de 0; linhas em branco e comentários `#` ou `//` não contam) |
| `D` | pilha de dados: guarda os valores manipulados |
| `i` | registrador de programa: próxima instrução |
| `s` | topo da pilha `D` |
| `b` | base do *frame* da função em execução |

Valores: inteiros em 64 bits (com estouro "dando a volta", como Go), reais, textos. Booleanos: **0 é falso, 1 é verdadeiro**.

### 6.1 Instruções

**Do conjunto original (slides da disciplina):**

| Grupo | Instruções |
|---|---|
| Controle | `INPP` `PARA` |
| Dados | `ALME m` `CRCT k` `CRVL n` `ARMZ n` |
| Aritmética | `SOMA` `SUBT` `MULT` `DIVI` `INVE` |
| Lógica | `CONJ` `DISJ` `NEGA` |
| Comparação | `CPME` `CPMA` `CPIG` `CDES` `CPMI` `CMAI` |
| Desvio | `DSVI p` `DSVF p` |
| Entrada/saída | `LEIT` `IMPR` |

**Acrescentadas para suportar Go:**

| Instrução | Função |
|---|---|
| `CRVF n` / `ARMF n` | carregar / armazenar variável **local** (endereço `b + n`) |
| `ENPR n` / `CHPR p` / `RTPR n` | entrada, chamada e retorno de função |
| `DESM n` | descarta `n` valores do topo |
| `MODU` | resto da divisão (com o sinal do dividendo, como em Go) |
| `EBIT` `OUBIT` `XORB` `LIMP` `DESE` `DESD` `NBIT` | `&` `\|` `^` `&^` `<<` `>>` e `^x` |
| `CONV tipo` | converte o topo para `int`, `float64`, `rune` ou `string` |
| `IMPB` | imprime o topo como `true`/`false` |
| `QUEB` | imprime quebra de linha |
| `FMT n` | `Sprintf`: usa `n` valores e o formato logo abaixo |

> `DIVI` com inteiros **trunca para zero**, como Go (`-7 / 2 = -3`). `SOMA` também concatena textos.
> `CONJ`, `DISJ` e `LEIT` existem na máquina, mas **este compilador não as gera**: `&&` e `||` usam desvios (curto-circuito) e a linguagem não tem entrada de dados.

### 6.2 Erros de execução tratados

Divisão por zero · pilha vazia · endereço de memória inválido · destino de salto fora do código · instrução desconhecida · argumento ausente ou inválido · deslocamento de bits negativo · estouro de pilha (recursão infinita; limite de 1.000.000 posições) · programa que termina sem `PARA`.

---

## 7. Como executar

**Pré-requisitos:** Python **3.10 ou superior** e um terminal aberto na **pasta raiz** do projeto. Não há dependências externas (só a biblioteca padrão). Desenvolvido com Python 3.14.

> A exigência da 3.10 vem de dois motivos: a máquina virtual usa `list[Instrucao]` (3.9+) e, até a 3.9, a biblioteca padrão tinha um módulo `parser` que poderia conflitar com a pasta `parser/` do projeto (ele foi removido na 3.10). Não foi testado em versões anteriores.

### 7.1 Criar o programa de entrada

Crie um arquivo `.go` dentro das regras da seção 2. Exemplo, `teste.go`:

```go
package main

import "fmt"

func main() {
    var x int = 10
    var y int = 5
    fmt.Println(x + y)
}
```

### 7.2 Compilar e executar

Um único comando compila o programa, grava o `.obj` e já o executa na máquina virtual:

```bash
python3 main.py teste.go
```

Saída esperada:

```
Código objeto gerado: programa.obj (n instruções)
--- Execução ---
15
```

Opções:

```bash
python3 main.py teste.go saida.obj      # escolhe o nome do arquivo objeto
python3 main.py teste.go --compilar     # só compila, não executa
python3 maqhipo/maquina.py programa.obj # executa um .obj já gerado
```

| Argumento do `main.py` | Significado | Padrão se omitido |
|---|---|---|
| 1º (`teste.go`) | arquivo Go de entrada | **obrigatório** (sem ele aparece `Uso: python main.py <arquivo.go> [arquivo.obj] [--compilar]`) |
| 2º (`programa.obj`) | arquivo objeto de saída | `programa.obj` |
| `--compilar` | gera o `.obj` e **não** executa | executa |

Em caso de erro (arquivo inexistente, léxico, sintático, semântico ou da máquina virtual), o `main.py` imprime a mensagem e termina com código de saída 1; a execução só começa se a compilação terminou sem erros.

### 7.3 Se houver erros

O compilador mostra todos os erros da fase em que parou e **não gera o `.obj`**:

```
Erros semânticos encontrados:
 - Erro semântico na linha 4, coluna 17: 'x' não foi declarado
```

---

## 8. Testes realizados

O arquivo `testar.py` roda **30 programas Go** pelo fluxo completo (lexer → parser → AST → semântico → gerador → máquina virtual) e compara a saída com o resultado esperado:

```bash
python3 testar.py          # roda todos
python3 testar.py 05 06    # roda só os testes 05 e 06
```

Resultado: **30 de 30 programas com a saída esperada.** O script termina imprimindo `TUDO OK` (ou `N falha(s)`).

| Área testada | Programas |
|---|---|
| Aritmética, `%`, bits (`\| & ^ &^ << >>`), operadores unários | 01, 11, 22, 23, 29 |
| `if`, `else`, `else if`, `if` com inicialização | 02, 14, 20 |
| `for` (condição, completo, infinito), `break`, `continue` | 03, 04, 18 |
| Funções: parâmetros, retorno, recursão (fatorial, fibonacci), chamadas aninhadas, uso antes da definição, sem retorno | 05, 06, 07, 17, 27 |
| Retorno múltiplo e atribuição múltipla (`a, b = b, a`) | 08, 12 |
| Variáveis globais, `const`, declaração `var` múltipla | 09, 19, 26, 30 |
| `float64` e conversões | 10, 30 |
| Atribuições compostas, `++`, `--` | 11, 24 |
| Strings, bool, comparação de texto | 13, 25 |
| `Println`, `Print`, `Printf`, `Sprintf` | 13, 15, 21, 28 |
| Curto-circuito de `&&` e `\|\|` | 13, 16 |

**Programas inválidos** (cada fase rejeita com mensagem clara): caractere inválido, `struct`, `switch`, falta de `}`, condição de `if` inválida, tipo incompatível, variável não usada, `import` não suportado, falta de `main`, indexação (tabela da seção 3.4).

Verificação adicional: os **66 desvios** (`DSVI`/`DSVF`/`CHPR`) gerados pelos 20 primeiros programas foram conferidos automaticamente: todos apontam para dentro do código e todo `CHPR` cai em um `ENPR`.

Não há testes separados por módulo: o `testar.py` exercita todas as fases de uma vez.

---

## 9. Limitações conhecidas

- Só o subconjunto da seção 2.1 é aceito; o restante de Go gera erro.
- Um único arquivo, um único pacote (`main`) e um único pacote importável (`fmt`).
- Sem entrada de dados pelo teclado.
- Sem arrays, slices, mapas, structs, ponteiros, métodos, closures ou concorrência.
- Valores e variáveis ocupam uma posição da pilha cada (não há tipos compostos).
- Strings e runes só aceitam os escapes listados na seção 5.1 (não há `\u`, `\x`).
- `fmt.Print` imprime os valores sem inserir espaços entre eles (o Go insere entre operandos que não são texto).
- `fmt.Printf` aceita os formatos `%d %s %v %f %t %c %q %%` (com largura, precisão e flags `-` e `0`).
- Na máquina virtual `bool` é 0/1: `Println` e `Print` mostram `true`/`false` (o tipo é conhecido na compilação), mas `Printf("%v", b)` imprime `1` ou `0`; use `%t`.
- `rune` é tratado como número: `fmt.Println('a')` imprime `97`, igual ao Go.
- A análise semântica cobre só as regras listadas na seção 5.4.
- Constantes sem tipo seguem regras mais simples que as do Go (seção 5.4).
- Os erros léxicos e semânticos são acumulados; o sintático **para no primeiro** erro encontrado.

---

## 10. Uso de Inteligência Artificial

Declaro que usei ferramentas de IA neste trabalho:

| Ferramenta | Como foi usada |
|---|---|
| **ChatGPT** | ajuda com trechos de código, esclarecimento de conceitos de compiladores, orientação sobre a execução do trabalho e revisão |
| **Claude** (Anthropic) | geração de parte de código, revisão e refinamento (incluindo seus testes), análise e execução de testes, e revisão desta documentação |

O código foi revisado, implementado gradativamente e testado por mim. 
