# ============================================================
# ANALISADOR SINTÁTICO SLR(1) - SHIFT-REDUCE
# ============================================================

from types import SimpleNamespace

from parser.grammar import simbolo_do_token, FIM_DA_ENTRADA


class ErroSintatico(Exception):
    """
    Erro encontrado durante a análise sintática.

    Além da mensagem, guarda a posição e os tokens esperados, para que
    outras partes do compilador (ou os testes) possam usá-los.
    """

    def __init__(self, mensagem, linha=None, coluna=None,
                 lexema=None, esperados=None):
        super().__init__(mensagem)
        self.linha = linha
        self.coluna = coluna
        self.lexema = lexema
        self.esperados = esperados if esperados is not None else []


class NoArvoreSintatica:
    """
    Nó da árvore sintática.

    Nós internos representam não terminais.
    Folhas representam tokens consumidos pelo parser.
    """

    def __init__(self, simbolo, filhos=None, token=None, producao=None):
        self.simbolo = simbolo
        self.filhos = filhos if filhos is not None else []
        self.token = token
        self.producao = producao

    def mostrar(self, nivel=0):
        """Imprime a árvore com indentação."""
        espacos = "  " * nivel

        if self.token is not None:
            print(
                f"{espacos}{self.simbolo}: "
                f"{self.token.lexema!r}"
            )
            return

        if self.producao is not None:
            lado_direito = (
                " ".join(self.producao[1])
                if self.producao[1]
                else "ε"
            )
            print(
                f"{espacos}{self.simbolo} "
                f"(produção: {self.simbolo} -> {lado_direito})"
            )
        else:
            print(f"{espacos}{self.simbolo}")

        for filho in self.filhos:
            filho.mostrar(nivel + 1)


class Parser:
    """
    Executa a análise sintática SLR(1).

    Pilha de estados:
        [0, estado, estado, ...]
        (sempre tem um elemento a mais que a pilha de nós: o estado 0)

    Pilha de nós:
        contém os nós correspondentes aos símbolos reconhecidos.

    O parser consulta ACTION para decidir SHIFT, REDUCE ou ACCEPT,
    e consulta GOTO depois de cada redução.
    """

    def __init__(self, gramatica, tabela):
        self.gramatica = gramatica
        self.tabela = tabela

    # --------------------------------------------------------
    # Entrada
    # --------------------------------------------------------

    def _adicionar_fim_entrada(self, tokens):
        """Garante que exista exatamente um marcador EOF ao final."""
        tokens = list(tokens)

        if tokens and tokens[-1].tipo == "EOF":
            return tokens

        if tokens:
            ultimo = tokens[-1]
            linha = getattr(ultimo, "linha", 1)
            coluna = getattr(ultimo, "coluna", 1)
        else:
            linha = 1
            coluna = 1

        tokens.append(
            SimpleNamespace(
                tipo="EOF",
                lexema="",
                linha=linha,
                coluna=coluna
            )
        )

        return tokens

    # --------------------------------------------------------
    # Erros
    # --------------------------------------------------------

    def _erro_sintatico(self, estado, token, simbolo):
        """Monta um erro com posição e tokens esperados."""
        esperados = sorted(
            terminal
            for (estado_tabela, terminal) in self.tabela.action
            if estado_tabela == estado
        )

        linha = getattr(token, "linha", "?")
        coluna = getattr(token, "coluna", "?")

        # O EOF não tem texto: dizemos "fim do arquivo" em vez de ''.
        if simbolo == FIM_DA_ENTRADA:
            encontrado = "fim do arquivo"
            lexema = ""
        else:
            lexema = getattr(token, "lexema", simbolo)
            encontrado = f"token {lexema!r}"

        if esperados:
            texto_esperados = ", ".join(esperados)
        else:
            texto_esperados = "nenhum terminal disponível"

        return ErroSintatico(
            f"Erro sintático na linha {linha}, coluna {coluna}: "
            f"{encontrado} inesperado. "
            f"Esperado: {texto_esperados}.",
            linha=linha,
            coluna=coluna,
            lexema=lexema,
            esperados=esperados
        )

    # --------------------------------------------------------
    # Algoritmo principal
    # --------------------------------------------------------

    def analisar(self, tokens, mostrar_passos=False):
        """
        Analisa a lista de tokens.

        'tokens' deve ser APENAS a lista de tokens. O Lexer.analisar()
        devolve (tokens, erros): desempacote antes de chamar.

        Retorna a raiz da árvore sintática se a entrada for aceita.
        Lança ErroSintatico se encontrar uma entrada inválida.
        """

        # Erro comum: passar o retorno inteiro do Lexer (uma tupla).
        if isinstance(tokens, tuple):
            raise TypeError(
                "analisar() recebeu uma tupla. Use: "
                "tokens, erros = Lexer(codigo).analisar() "
                "e passe apenas 'tokens'."
            )

        if not self.tabela.action:
            raise RuntimeError(
                "A tabela SLR(1) está vazia. "
                "Execute tabela.construir() antes de analisar."
            )

        if self.tabela.conflitos:
            raise RuntimeError(
                "A tabela SLR(1) possui conflitos. "
                "Corrija os conflitos antes de executar o parser."
            )

        tokens = self._adicionar_fim_entrada(tokens)

        # A pilha começa no estado inicial 0.
        pilha_estados = [0]

        # Guarda os nós da árvore correspondentes aos símbolos reduzidos.
        pilha_nos = []

        # Índice do próximo token de entrada.
        indice_token = 0

        while True:
            estado_atual = pilha_estados[-1]
            token_atual = tokens[indice_token]
            simbolo_atual = simbolo_do_token(token_atual)

            acao = self.tabela.action.get(
                (estado_atual, simbolo_atual)
            )

            if acao is None:
                raise self._erro_sintatico(
                    estado_atual,
                    token_atual,
                    simbolo_atual
                )

            tipo_acao, valor = acao

            if mostrar_passos:
                print(
                    f"Estado: {estado_atual} | "
                    f"Token: {simbolo_atual} | "
                    f"Ação: {self.tabela.descrever_acao(acao)}"
                )

            # ------------------------------------------------
            # SHIFT
            # ------------------------------------------------
            if tipo_acao == "SHIFT":
                # O token é reconhecido e seu nó vai para a pilha.
                pilha_nos.append(
                    NoArvoreSintatica(
                        simbolo=simbolo_atual,
                        token=token_atual
                    )
                )

                # Empilha o estado de destino.
                pilha_estados.append(valor)

                # Avança para o próximo token.
                indice_token += 1

            # ------------------------------------------------
            # REDUCE
            # ------------------------------------------------
            elif tipo_acao == "REDUCE":
                indice_producao = valor

                nao_terminal, alternativa = (
                    self.gramatica.lista_producoes[indice_producao]
                )

                quantidade_simbolos = len(alternativa)

                # Retira da pilha os nós correspondentes ao lado
                # direito da produção.
                if quantidade_simbolos:
                    filhos = pilha_nos[-quantidade_simbolos:]
                    del pilha_nos[-quantidade_simbolos:]

                    # Remove um estado para cada símbolo retirado.
                    del pilha_estados[-quantidade_simbolos:]
                else:
                    # Produção vazia: não remove nenhum elemento.
                    filhos = []

                # Cria um nó para o lado esquerdo da produção.
                novo_no = NoArvoreSintatica(
                    simbolo=nao_terminal,
                    filhos=filhos,
                    producao=(nao_terminal, alternativa)
                )

                pilha_nos.append(novo_no)

                # Depois da redução, consulta GOTO.
                estado_anterior = pilha_estados[-1]
                novo_estado = self.tabela.goto.get(
                    (estado_anterior, nao_terminal)
                )

                if novo_estado is None:
                    raise RuntimeError(
                        "Erro interno do parser: não existe GOTO para "
                        f"({estado_anterior}, {nao_terminal})."
                    )

                pilha_estados.append(novo_estado)

            # ------------------------------------------------
            # ACCEPT
            # ------------------------------------------------
            elif tipo_acao == "ACCEPT":
                if len(pilha_nos) != 1:
                    raise RuntimeError(
                        "A entrada foi aceita, mas a pilha da árvore "
                        "não contém exatamente uma raiz."
                    )

                if mostrar_passos:
                    print("Entrada aceita!")

                return pilha_nos[0]

            else:
                raise RuntimeError(
                    f"Tipo de ação desconhecido: {tipo_acao}"
                )


# ============================================================
# MONTAGEM DO PARSER
# ============================================================

def criar_parser(gramatica):
    """
    Monta todo o pipeline de construção e devolve um Parser pronto:

        FIRST/FOLLOW -> autômato LR(0) -> tabela SLR(1) -> Parser

    Levanta RuntimeError (com a lista de conflitos) se a gramática
    não for SLR(1).
    """
    # Imports aqui dentro para o módulo continuar leve de importar.
    from parser.first_follow import FirstFollow
    from parser.lr0 import AutomatoLR0
    from parser.parsing_table import TabelaSLR

    analisador_first_follow = FirstFollow(gramatica)
    analisador_first_follow.calcular()

    automato = AutomatoLR0(gramatica)
    automato.construir()

    tabela = TabelaSLR(automato, analisador_first_follow)
    tabela.construir()

    if tabela.conflitos:
        tabela.mostrar_conflitos()
        raise RuntimeError(
            "A gramática não é SLR(1): veja os conflitos acima."
        )

    return Parser(gramatica, tabela)
