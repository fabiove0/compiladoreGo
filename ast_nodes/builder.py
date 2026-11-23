
# ============================================================
# CONSTRUTOR DA AST (ÁRVORE SINTÁTICA -> AST)
# ============================================================
#
# Visão geral:
#
#   O parser SLR(1) devolve uma árvore de DERIVAÇÃO: um nó para cada
#   regra usada, com todos os tokens (inclusive ";" e ","), listas
#   recursivas à esquerda e a cadeia de precedência das expressões.
#
#   Este módulo percorre essa árvore e monta a AST enxuta definida em
#   nodes.py. Três tipos de simplificação acontecem aqui:
#
#   1) LISTAS RECURSIVAS viram listas Python.
#        ListaExpr -> ListaExpr , Expr | Expr       ==>   [expr, expr, ...]
#
#   2) CADEIAS DE PRECEDÊNCIA são colapsadas.
#        Expr -> ExprOu -> ExprE -> ... -> Operando  ==>   o nó do meio
#      (só vira Binaria/Unaria quando existe de fato um operador).
#
#   3) LITERAIS viram valores de verdade.
#        "0x1F" vira 31, "\n" dentro de string vira quebra de linha.
#

 
try:
    from . import nodes
except ImportError:
    import nodes
 
 
# ============================================================
# 1. ERRO
# ============================================================
 
class ErroAST(Exception):
    """
    Erro ao montar a AST.
 
    A gramática aceita um pouco mais do que Go aceita (para a tabela SLR
    não ter conflitos). Quando o excesso não cabe em nenhum nó da AST,
    o erro é avisado aqui, com a posição do problema. Exemplos:
        - "if x := 5 { }"   (a condição não é uma expressão)
        - "a, b"            (lista de expressões usada como comando)
    """
 
    def __init__(self, mensagem, linha=None, coluna=None):
        if linha is not None:
            texto = f"Erro na linha {linha}, coluna {coluna}: {mensagem}"
        else:
            texto = mensagem
 
        super().__init__(texto)
        self.mensagem = mensagem
        self.linha = linha
        self.coluna = coluna
 
 
# ============================================================
# 2. TABELAS DE CONVERSÃO DE LITERAIS
# ============================================================
 
# Escapes aceitos pelo lexer em strings: \a \b \f \n \r \t \v \\ \"
ESCAPES_STRING = {
    "a": "\a", "b": "\b", "f": "\f", "n": "\n",
    "r": "\r", "t": "\t", "v": "\v", "\\": "\\", '"': '"',
}
 
# Escapes aceitos pelo lexer em runes: iguais, mas com \' no lugar de \"
ESCAPES_RUNE = {
    "a": "\a", "b": "\b", "f": "\f", "n": "\n",
    "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'",
}
 
# Tokens que só separam itens das listas (não entram na AST)
SEPARADORES = {",", ";"}
 
 
# ============================================================
# 3. CONSTRUTOR
# ============================================================
 
class ConstrutorAST:
    """
    Percorre a árvore de derivação (NoArvoreSintatica) e devolve a AST.
 
    Para cada não terminal da gramática existe um método
    _construir_<NomeDaRegra>. O método construir() escolhe qual chamar
    olhando o campo "simbolo" do nó.
 
    Em geral, cada método descobre QUAL alternativa da regra foi usada
    olhando a quantidade de filhos (ou o símbolo de algum deles), porque
    cada alternativa da gramática tem um formato diferente.
    """
 
    # --------------------------------------------------------
    # Despacho
    # --------------------------------------------------------
 
    def construir(self, no):
        """Constrói o nó da AST correspondente a um nó da árvore."""
        metodo = getattr(self, "_construir_" + no.simbolo, None)
 
        if metodo is None:
            linha, coluna = self._posicao(no)
            raise ErroAST(
                f"Construtor da AST não conhece a regra {no.simbolo!r}.",
                linha,
                coluna
            )
 
        return metodo(no)
 
    # --------------------------------------------------------
    # Funções auxiliares
    # --------------------------------------------------------
 
    def _primeiro_token(self, no):
        """Primeiro token (da esquerda) abaixo de um nó, ou None."""
        if no.token is not None:
            return no.token
 
        for filho in no.filhos:
            token = self._primeiro_token(filho)
            if token is not None:
                return token
 
        return None
 
    def _posicao(self, no):
        """(linha, coluna) do primeiro token do nó. Usada nos nós da AST."""
        token = self._primeiro_token(no)
 
        if token is None:
            return None, None
 
        return token.linha, token.coluna
 
    def _itens_da_lista(self, no):
        """
        Transforma uma lista recursiva à esquerda numa lista Python.
 
        Serve para todas as regras do tipo:
            Lista -> Lista [sep] Item [sep]
            Lista -> Item
            Lista -> ε
 
        Devolve só os ITENS (nós da árvore), na ordem do código, sem os
        separadores "," e ";".
        """
        grupos = []
 
        # Desce pela esquerda: cada passo guarda o que sobrou à direita.
        while no is not None:
            if no.filhos and no.filhos[0].simbolo == no.simbolo:
                grupos.append(no.filhos[1:])
                no = no.filhos[0]
            else:
                grupos.append(no.filhos)
                no = None
 
        # Fomos do último item para o primeiro: inverte para a ordem certa.
        grupos.reverse()
 
        itens = []
        for grupo in grupos:
            for filho in grupo:
                if filho.token is not None and filho.simbolo in SEPARADORES:
                    continue
                itens.append(filho)
 
        return itens
 
    def _nomes(self, no_lista_ids):
        """ListaIds -> lista de str. Exemplo: a, b, c -> ["a", "b", "c"]."""
        return [
            folha.token.lexema
            for folha in self._itens_da_lista(no_lista_ids)
        ]
 
    def _expressoes(self, no_lista_expr):
        """ListaExpr -> lista de nós de expressão."""
        return [
            self.construir(expr)
            for expr in self._itens_da_lista(no_lista_expr)
        ]
 
    def _lexema(self, no):
        """Texto do token de uma folha."""
        return no.token.lexema
 
    # --------------------------------------------------------
    # Conversão dos literais
    # --------------------------------------------------------
 
    def _valor_inteiro(self, token):
        """'0x1F' -> 31, '0b101' -> 5, '0755' -> 493, '1_000' -> 1000."""
        texto = token.lexema.replace("_", "")
 
        try:
            if len(texto) > 1 and texto[0] == "0" and texto[1] in "xXbBoO":
                return int(texto, 0)
 
            # Em Go, um zero na frente (0755) significa octal.
            if len(texto) > 1 and texto[0] == "0":
                return int(texto, 8)
 
            return int(texto)
 
        except ValueError:
            raise ErroAST(
                f"Literal inteiro inválido: {token.lexema!r}.",
                token.linha,
                token.coluna
            )
 
    def _valor_real(self, token):
        """'3.14' -> 3.14, '.5' -> 0.5, '2.5e-3' -> 0.0025."""
        try:
            return float(token.lexema.replace("_", ""))
        except ValueError:
            raise ErroAST(
                f"Literal real inválido: {token.lexema!r}.",
                token.linha,
                token.coluna
            )
 
    def _valor_string(self, token):
        """
        Tira as aspas e interpreta os escapes.
        '"a\\nb"' (com as aspas) -> a, quebra de linha, b.
        """
        corpo = token.lexema[1:-1]
        resultado = []
        i = 0
 
        while i < len(corpo):
            caractere = corpo[i]
 
            if caractere == "\\" and i + 1 < len(corpo):
                escape = corpo[i + 1]
                resultado.append(ESCAPES_STRING.get(escape, escape))
                i += 2
            else:
                resultado.append(caractere)
                i += 1
 
        return "".join(resultado)
 
    def _valor_rune(self, token):
        """
        Código Unicode do caractere. Exemplos:
            'a' -> 97     '\\n' -> 10     '\\000' -> 0
        """
        corpo = token.lexema[1:-1]
 
        if corpo.startswith("\\"):
            resto = corpo[1:]
 
            if resto in ESCAPES_RUNE:
                return ord(ESCAPES_RUNE[resto])
 
            if resto and all(c in "01234567" for c in resto):
                valor = int(resto, 8)
                if valor <= 255:
                    return valor
 
        elif len(corpo) == 1:
            return ord(corpo)
 
        raise ErroAST(
            f"Literal rune inválido: {token.lexema!r}.",
            token.linha,
            token.coluna
        )
 
    # ========================================================
    # PROGRAMA E DECLARAÇÕES GLOBAIS
    # ========================================================
 
    def _construir_Programa(self, no):
        # Programa -> DeclPacote ListaImports ListaDeclGlobais
        decl_pacote, lista_imports, lista_globais = no.filhos
 
        # DeclPacote -> package IDENTIFICADOR ;
        pacote = self._lexema(decl_pacote.filhos[1])
 
        imports = [
            self.construir(item)
            for item in self._itens_da_lista(lista_imports)
        ]
 
        declaracoes = [
            self.construir(item)
            for item in self._itens_da_lista(lista_globais)
        ]
 
        linha, coluna = self._posicao(no)
        return nodes.Programa(pacote, imports, declaracoes, linha, coluna)
 
    def _construir_Import(self, no):
        # import STRING ;
        # import IDENTIFICADOR STRING ;
        linha, coluna = self._posicao(no)
 
        if len(no.filhos) == 3:
            apelido = None
            token_caminho = no.filhos[1].token
        else:
            apelido = self._lexema(no.filhos[1])
            token_caminho = no.filhos[2].token
 
        caminho = self._valor_string(token_caminho)
        return nodes.Import(caminho, apelido, linha, coluna)
 
    def _construir_DeclGlobal(self, no):
        # DeclGlobal -> DeclVar | DeclConst | DeclFuncao
        return self.construir(no.filhos[0])
 
    # ========================================================
    # VARIÁVEIS, CONSTANTES E TIPOS
    # ========================================================
 
    def _construir_DeclVar(self, no):
        # DeclVar -> var EspecVar
        #
        # EspecVar tem três formatos (pela quantidade de filhos):
        #   2 filhos: ListaIds Tipo                    x int
        #   3 filhos: ListaIds = ListaExpr             x = 5
        #   4 filhos: ListaIds Tipo = ListaExpr        x int = 5
        espec = no.filhos[1]
        filhos = espec.filhos
 
        nomes = self._nomes(filhos[0])
        tipo = None
        valores = []
 
        if len(filhos) == 2:
            tipo = self.construir(filhos[1])
        elif len(filhos) == 3:
            valores = self._expressoes(filhos[2])
        else:
            tipo = self.construir(filhos[1])
            valores = self._expressoes(filhos[3])
 
        linha, coluna = self._posicao(no)
        return nodes.DeclVar(nomes, tipo, valores, linha, coluna)
 
    def _construir_DeclConst(self, no):
        # DeclConst -> const EspecConst
        #
        # EspecConst:
        #   3 filhos: ListaIds = ListaExpr             pi = 3.14
        #   4 filhos: ListaIds Tipo = ListaExpr        n int = 10
        espec = no.filhos[1]
        filhos = espec.filhos
 
        nomes = self._nomes(filhos[0])
        tipo = None
 
        if len(filhos) == 3:
            valores = self._expressoes(filhos[2])
        else:
            tipo = self.construir(filhos[1])
            valores = self._expressoes(filhos[3])
 
        linha, coluna = self._posicao(no)
        return nodes.DeclConst(nomes, tipo, valores, linha, coluna)
 
    def _construir_Tipo(self, no):
        # Tipo -> IDENTIFICADOR
        folha = no.filhos[0]
        return nodes.Tipo(
            self._lexema(folha),
            folha.token.linha,
            folha.token.coluna
        )
 
    # ========================================================
    # FUNÇÕES
    # ========================================================
 
    def _construir_DeclFuncao(self, no):
        # func IDENTIFICADOR ( Parametros ) TipoRetorno Bloco
        #  0        1        2      3      4      5       6
        nome = self._lexema(no.filhos[1])
        parametros = self._construir_Parametros(no.filhos[3])
        tipos_retorno = self._construir_TipoRetorno(no.filhos[5])
        corpo = self.construir(no.filhos[6])
 
        linha, coluna = self._posicao(no)
        return nodes.DeclFuncao(
            nome, parametros, tipos_retorno, corpo, linha, coluna
        )
 
    def _construir_Parametros(self, no):
        """
        Parametros -> ListaParametros | ε
 
        Devolve uma lista de Parametro com UM nome cada: o grupo
        "a, b int" vira dois nós, (a int) e (b int).
        """
        if not no.filhos:
            return []
 
        parametros = []
 
        for grupo in self._itens_da_lista(no.filhos[0]):
            # Parametro -> ListaIds Tipo
            nomes_ids = self._itens_da_lista(grupo.filhos[0])
            tipo_original = self.construir(grupo.filhos[1])
 
            for folha in nomes_ids:
                # Um Tipo novo para cada parâmetro: assim os nós não
                # ficam compartilhados entre pais diferentes.
                tipo = nodes.Tipo(
                    tipo_original.nome,
                    tipo_original.linha,
                    tipo_original.coluna
                )
                parametros.append(
                    nodes.Parametro(
                        self._lexema(folha),
                        tipo,
                        folha.token.linha,
                        folha.token.coluna
                    )
                )
 
        return parametros
 
    def _construir_TipoRetorno(self, no):
        """
        TipoRetorno -> ε | Tipo | ( ListaTipos )
        Devolve uma lista de Tipo (vazia se a função não retorna nada).
        """
        if not no.filhos:
            return []
 
        if len(no.filhos) == 1:
            return [self.construir(no.filhos[0])]
 
        return [
            self.construir(tipo)
            for tipo in self._itens_da_lista(no.filhos[1])
        ]
 
    # ========================================================
    # BLOCO E COMANDOS
    # ========================================================
 
    def _construir_Bloco(self, no):
        # { ListaComandos }                  -> 3 filhos
        # { ListaComandos Comando }          -> 4 filhos (último sem ";")
        comandos = [
            self.construir(item)
            for item in self._itens_da_lista(no.filhos[1])
        ]
 
        if len(no.filhos) == 4:
            comandos.append(self.construir(no.filhos[2]))
 
        linha, coluna = self._posicao(no)
        return nodes.Bloco(comandos, linha, coluna)
 
    def _construir_Comando(self, no):
        # Comando -> DeclVar | DeclConst | ComandoSimples | ComandoReturn
        #          | ComandoIf | ComandoFor | Bloco | ComandoBreak
        #          | ComandoContinue
        return self.construir(no.filhos[0])
 
    def _construir_ComandoSimples(self, no):
        filhos = no.filhos
        linha, coluna = self._posicao(no)
 
        # ListaExpr  ->  comando que é só uma expressão (ex.: chamada)
        if len(filhos) == 1 and filhos[0].simbolo == "ListaExpr":
            expressoes = self._expressoes(filhos[0])
 
            if len(expressoes) != 1:
                raise ErroAST(
                    "Uma lista de expressões não pode ser usada "
                    "como comando.",
                    linha,
                    coluna
                )
 
            return nodes.ComandoExpressao(expressoes[0], linha, coluna)
 
        # Atribuicao
        if len(filhos) == 1:
            return self.construir(filhos[0])
 
        # ListaExpr := ListaExpr
        if filhos[1].simbolo == ":=":
            return nodes.DeclaracaoCurta(
                self._expressoes(filhos[0]),
                self._expressoes(filhos[2]),
                linha,
                coluna
            )
 
        # Expr ++      Expr --
        return nodes.IncDec(
            self.construir(filhos[0]),
            self._lexema(filhos[1]),
            linha,
            coluna
        )
 
    def _construir_Atribuicao(self, no):
        # ListaExpr operador ListaExpr
        linha, coluna = self._posicao(no)
 
        return nodes.Atribuicao(
            self._expressoes(no.filhos[0]),
            self._lexema(no.filhos[1]),
            self._expressoes(no.filhos[2]),
            linha,
            coluna
        )
 
    def _construir_ComandoReturn(self, no):
        # return          |   return ListaExpr
        linha, coluna = self._posicao(no)
 
        valores = []
        if len(no.filhos) == 2:
            valores = self._expressoes(no.filhos[1])
 
        return nodes.Return(valores, linha, coluna)
 
    def _construir_ComandoBreak(self, no):
        linha, coluna = self._posicao(no)
        return nodes.Break(linha, coluna)
 
    def _construir_ComandoContinue(self, no):
        linha, coluna = self._posicao(no)
        return nodes.Continue(linha, coluna)
 
    # --------------------------------------------------------
    # if
    # --------------------------------------------------------
 
    def _condicao_de_comando_simples(self, comando, nome_comando):
        """
        Em "if x > 0 {" e "for x < 10 {" a condição chega como um
        ComandoSimples. Aqui conferimos que ele é só uma expressão e
        devolvemos essa expressão.
        """
        if not isinstance(comando, nodes.ComandoExpressao):
            raise ErroAST(
                f"A condição do {nome_comando} deve ser uma expressão.",
                comando.linha,
                comando.coluna
            )
 
        return comando.expressao
 
    def _construir_CabecalhoIf(self, no):
        """
        Devolve (inicializacao, condicao).
 
            x > 0                    -> (None, x > 0)
            z := soma(a, b); z > 5   -> (z := ..., z > 5)
        """
        comando = self.construir(no.filhos[0])
 
        if len(no.filhos) == 1:
            return None, self._condicao_de_comando_simples(comando, "if")
 
        return comando, self.construir(no.filhos[2])
 
    def _construir_ComandoIf(self, no):
        # if CabecalhoIf Bloco                         -> 3 filhos
        # if CabecalhoIf Bloco else Bloco              -> 5 filhos
        # if CabecalhoIf Bloco else ComandoIf          -> 5 filhos
        inicializacao, condicao = self._construir_CabecalhoIf(no.filhos[1])
        entao = self.construir(no.filhos[2])
 
        senao = None
        if len(no.filhos) == 5:
            senao = self.construir(no.filhos[4])
 
        linha, coluna = self._posicao(no)
        return nodes.If(inicializacao, condicao, entao, senao, linha, coluna)
 
    # --------------------------------------------------------
    # for
    # --------------------------------------------------------
 
    def _construir_ComandoFor(self, no):
        # for Bloco                      -> laço infinito
        # for ComandoSimples Bloco       -> só condição
        # for CabecalhoFor Bloco         -> for completo
        linha, coluna = self._posicao(no)
 
        if len(no.filhos) == 2:
            corpo = self.construir(no.filhos[1])
            return nodes.For(None, None, None, corpo, linha, coluna)
 
        corpo = self.construir(no.filhos[2])
        meio = no.filhos[1]
 
        if meio.simbolo == "ComandoSimples":
            comando = self.construir(meio)
            condicao = self._condicao_de_comando_simples(comando, "for")
            return nodes.For(None, condicao, None, corpo, linha, coluna)
 
        inicializacao, condicao, passo = self._construir_CabecalhoFor(meio)
        return nodes.For(inicializacao, condicao, passo, corpo, linha, coluna)
 
    def _construir_CabecalhoFor(self, no):
        """
        CabecalhoFor -> ForInicio ; ForCondicao ; ForPasso
        Devolve (inicializacao, condicao, passo); cada um pode ser None.
        """
        inicio, _, condicao, _, passo = no.filhos
 
        return (
            self._parte_opcional(inicio),
            self._parte_opcional(condicao),
            self._parte_opcional(passo),
        )
 
    def _parte_opcional(self, no):
        """ForInicio / ForCondicao / ForPasso: ε ou um único filho."""
        if not no.filhos:
            return None
 
        return self.construir(no.filhos[0])
 
    # ========================================================
    # EXPRESSÕES
    # ========================================================
 
    def _construir_Expr(self, no):
        # Expr -> ExprOu
        return self.construir(no.filhos[0])
 
    def _construir_binaria(self, no):
        """
        Serve para todas as faixas de precedência:
            ExprOu, ExprE, ExprComparacao, ExprSoma, ExprProduto
 
        Com 3 filhos é uma operação (esquerda operador direita).
        Com 1 filho é só a faixa de baixo, então colapsamos.
        """
        if len(no.filhos) == 1:
            return self.construir(no.filhos[0])
 
        esquerda, operador, direita = no.filhos
 
        return nodes.Binaria(
            self._lexema(operador),
            self.construir(esquerda),
            self.construir(direita),
            operador.token.linha,    # erros apontam para o operador
            operador.token.coluna
        )
 
    _construir_ExprOu = _construir_binaria
    _construir_ExprE = _construir_binaria
    _construir_ExprComparacao = _construir_binaria
    _construir_ExprSoma = _construir_binaria
    _construir_ExprProduto = _construir_binaria
 
    def _construir_ExprUnaria(self, no):
        # ExprUnaria -> + ExprUnaria | - ... | ! ... | ^ ... | ExprPrimaria
        if len(no.filhos) == 1:
            return self.construir(no.filhos[0])
 
        operador, operando = no.filhos
 
        return nodes.Unaria(
            self._lexema(operador),
            self.construir(operando),
            operador.token.linha,
            operador.token.coluna
        )
 
    def _construir_ExprPrimaria(self, no):
        # Operando
        # ExprPrimaria . IDENTIFICADOR
        # ExprPrimaria ( Argumentos )
        # ExprPrimaria [ Expr ]
        filhos = no.filhos
 
        if len(filhos) == 1:
            return self.construir(filhos[0])
 
        linha, coluna = self._posicao(no)
        base = self.construir(filhos[0])
        simbolo = filhos[1].simbolo
 
        if simbolo == ".":
            return nodes.AcessoMembro(
                base, self._lexema(filhos[2]), linha, coluna
            )
 
        if simbolo == "(":
            return nodes.Chamada(
                base, self._construir_Argumentos(filhos[2]), linha, coluna
            )
 
        # "["
        return nodes.Indexacao(
            base, self.construir(filhos[2]), linha, coluna
        )
 
    def _construir_Argumentos(self, no):
        # Argumentos -> ListaExpr | ε
        if not no.filhos:
            return []
 
        return self._expressoes(no.filhos[0])
 
    def _construir_Operando(self, no):
        filhos = no.filhos
 
        # ( Expr )  ->  só a expressão de dentro (a árvore já guarda
        # a ordem das operações, os parênteses não são mais necessários)
        if len(filhos) == 3:
            return self.construir(filhos[1])
 
        folha = filhos[0]
        token = folha.token
        tipo = folha.simbolo
 
        if tipo == "IDENTIFICADOR":
            return nodes.Identificador(token.lexema, token.linha, token.coluna)
 
        if tipo == "NUMERO_INTEIRO":
            return nodes.LiteralInteiro(
                self._valor_inteiro(token),
                token.lexema,
                token.linha,
                token.coluna
            )
 
        if tipo == "NUMERO_REAL":
            return nodes.LiteralReal(
                self._valor_real(token),
                token.lexema,
                token.linha,
                token.coluna
            )
 
        if tipo == "STRING":
            return nodes.LiteralString(
                self._valor_string(token), token.linha, token.coluna
            )
 
        # RUNE
        return nodes.LiteralRune(
            self._valor_rune(token),
            token.lexema,
            token.linha,
            token.coluna
        )
 
 
# ============================================================
# 4. FUNÇÃO DE CONVENIÊNCIA
# ============================================================
 
def construir_ast(arvore_sintatica):
    """
    Recebe a raiz devolvida por Parser.analisar() e devolve o nó
    Programa da AST. Lança ErroAST se algo não couber na AST.
    """
    return ConstrutorAST().construir(arvore_sintatica)
 
