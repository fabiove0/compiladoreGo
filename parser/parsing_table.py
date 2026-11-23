# ============================================================
# CONSTRUÇÃO DA TABELA SLR(1) - ACTION E GOTO
# ============================================================
#
# Visão geral:
#
#   O autômato LR(0) já sabe "para onde ir" ao ler cada símbolo.
#   FOLLOW sabe "quando é seguro reduzir".
#   A tabela SLR junta as duas coisas num formato fácil para o parser:
#
#     ACTION[(estado, terminal)]      -> o que fazer com o próximo token
#     GOTO[(estado, nao_terminal)]    -> para onde ir depois de uma redução


class TabelaSLR:
    """
    Constrói as tabelas ACTION e GOTO a partir de:
      - uma instância de AutomatoLR0 já construído;
      - uma instância de FirstFollow com FIRST e FOLLOW calculados.

    Formato das ações (não mudou, o parser continua igual):
      ("SHIFT", estado_destino)
      ("REDUCE", indice_producao)
      ("ACCEPT", None)

    Cada conflito encontrado é um dicionário:
      {"estado", "terminal", "acao_existente", "nova_acao", "tipo"}
    onde "tipo" é "shift/reduce", "reduce/reduce" ou "outro".
    """

    def __init__(self, automato, first_follow):
        self.automato = automato
        self.first_follow = first_follow

        self.gramatica = automato.gramatica_original
        self.gramatica_aumentada = automato.gramatica

        self.action = {}
        self.goto = {}
        self.conflitos = []

        # Mapeia cada produção original para seu índice.
        # Esses índices serão usados nas ações REDUCE, e o parser usa
        # o MESMO índice em gramatica.lista_producoes para saber quantos
        # símbolos desempilhar e qual não terminal empilhar.
        self.indices_producoes = {
            (nao_terminal, alternativa): indice
            for indice, (nao_terminal, alternativa)
            in enumerate(self.gramatica.lista_producoes)
        }

    # ========================================================
    # 1. FUNÇÕES AUXILIARES
    # ========================================================

    @staticmethod
    def _classificar_conflito(acao_a, acao_b):
        """Diz se o conflito é shift/reduce, reduce/reduce ou outro."""
        tipos = {acao_a[0], acao_b[0]}

        if tipos == {"SHIFT", "REDUCE"}:
            return "shift/reduce"

        if tipos == {"REDUCE"}:
            return "reduce/reduce"

        return "outro"

    def descrever_producao(self, indice):
        """Texto legível da produção de índice 'indice'."""
        nao_terminal, alternativa = self.gramatica.lista_producoes[indice]
        lado_direito = " ".join(alternativa) if alternativa else "ε"
        return f"{nao_terminal} -> {lado_direito}"

    def descrever_acao(self, acao):
        """Texto legível de uma ação (ex.: 's12', 'r5 (A -> b c)')."""
        tipo, valor = acao

        if tipo == "SHIFT":
            return f"s{valor}"

        if tipo == "REDUCE":
            return f"r{valor} ({self.descrever_producao(valor)})"

        return "ACCEPT"

    def _registrar_action(self, estado, terminal, acao):
        """Insere uma ação e registra conflito se já houver outra diferente."""
        chave = (estado, terminal)
        acao_existente = self.action.get(chave)

        if acao_existente is None:
            self.action[chave] = acao

        elif acao_existente != acao:
            conflito = {
                "estado": estado,
                "terminal": terminal,
                "acao_existente": acao_existente,
                "nova_acao": acao,
                "tipo": self._classificar_conflito(acao_existente, acao),
            }

            if conflito not in self.conflitos:
                self.conflitos.append(conflito)

    # ========================================================
    # 2. CONSTRUÇÃO
    # ========================================================

    def construir(self):
        """Preenche ACTION e GOTO com base nos itens LR(0)."""

        if not self.automato.estados:
            raise ValueError(
                "O autômato LR(0) ainda não foi construído. "
                "Execute automato.construir() primeiro."
            )

        # Atenção: first_follow.first e .follow já nascem como dicionários
        # com conjuntos vazios, então "not first_follow.first" nunca era
        # verdadeiro. A propriedade "calculado" é a verificação correta.
        if not self.first_follow.calculado:
            raise ValueError(
                "FIRST e FOLLOW ainda não foram calculados. "
                "Execute first_follow.calcular() primeiro."
            )

        self.action.clear()
        self.goto.clear()
        self.conflitos.clear()

        inicio_aumentado = self.gramatica_aumentada.simbolo_inicial
        inicio_original = self.gramatica.simbolo_inicial

        # --- Passo 1: transições do autômato ---------------------
        #   - seta por TERMINAL      -> SHIFT  (empilha e avança)
        #   - seta por NÃO TERMINAL  -> GOTO   (usada após um REDUCE)
        #
        # sorted() só deixa a ordem de processamento previsível, para
        # que a lista de conflitos saia sempre igual entre execuções.
        for (estado_origem, simbolo), estado_destino in sorted(
            self.automato.transicoes.items(),
            key=lambda item: (item[0][0], item[0][1])
        ):
            if simbolo in self.gramatica.terminais:
                self._registrar_action(
                    estado_origem,
                    simbolo,
                    ("SHIFT", estado_destino)
                )

            elif simbolo in self.gramatica.nao_terminais:
                self.goto[(estado_origem, simbolo)] = estado_destino

            else:
                # Não deveria acontecer. Se acontecer, é bug no
                # autômato ou na gramática: melhor avisar do que
                # ignorar em silêncio.
                raise ValueError(
                    f"Símbolo {simbolo!r} da transição do estado "
                    f"{estado_origem} não é terminal nem não terminal."
                )

        # --- Passo 2: itens completos (ponto no fim) -------------
        #   - A -> alfa ·              -> REDUCE em cada terminal de FOLLOW(A)
        #   - Programa' -> Programa ·  -> ACCEPT quando o token for "$"
        for numero_estado, estado in enumerate(self.automato.estados):
            for nao_terminal, alternativa, posicao in estado:

                # O ponto ainda não chegou ao final da produção.
                if posicao != len(alternativa):
                    continue

                # Item completo da produção aumentada:
                # Programa' -> Programa .
                if (
                    nao_terminal == inicio_aumentado
                    and alternativa == (inicio_original,)
                ):
                    self._registrar_action(
                        numero_estado,
                        "$",
                        ("ACCEPT", None)
                    )
                    continue

                # Produção normal: A -> alfa .
                indice_producao = self.indices_producoes.get(
                    (nao_terminal, alternativa)
                )

                if indice_producao is None:
                    raise ValueError(
                        "Não foi possível localizar a produção "
                        f"{nao_terminal} -> {alternativa}"
                    )

                # Em SLR(1), REDUCE é inserido em FOLLOW(A).
                # sorted() mantém a saída determinística.
                for terminal in sorted(
                    self.first_follow.follow[nao_terminal]
                ):
                    self._registrar_action(
                        numero_estado,
                        terminal,
                        ("REDUCE", indice_producao)
                    )

        return self.action, self.goto

    # ========================================================
    # 3. EXIBIÇÃO
    # ========================================================

    def mostrar_resumo(self):
        """Quantidade de entradas de cada tipo (bom para conferir)."""
        total = {"SHIFT": 0, "REDUCE": 0, "ACCEPT": 0}

        for tipo, _ in self.action.values():
            total[tipo] += 1

        print("\n========== RESUMO DA TABELA ==========\n")
        print("Estados:           ", len(self.automato.estados))
        print("Ações SHIFT:       ", total["SHIFT"])
        print("Ações REDUCE:      ", total["REDUCE"])
        print("Ações ACCEPT:      ", total["ACCEPT"])
        print("Entradas GOTO:     ", len(self.goto))
        print("Conflitos:         ", len(self.conflitos))

    def mostrar_action(self):
        print("\n========== TABELA ACTION ==========\n")

        for (estado, terminal), acao in sorted(
            self.action.items(),
            key=lambda item: (item[0][0], item[0][1])
        ):
            print(
                f"ACTION[{estado}, {terminal}] = "
                f"{self.descrever_acao(acao)}"
            )

    def mostrar_goto(self):
        print("\n========== TABELA GOTO ==========\n")

        for (estado, nao_terminal), destino in sorted(
            self.goto.items(),
            key=lambda item: (item[0][0], item[0][1])
        ):
            print(f"GOTO[{estado}, {nao_terminal}] = {destino}")

    def mostrar_conflitos(self):
        print("\n========== CONFLITOS SLR(1) ==========\n")

        if not self.conflitos:
            print("Nenhum conflito encontrado.")
            return

        for conflito in self.conflitos:
            print(
                f"[{conflito['tipo']}] "
                f"Estado {conflito['estado']}, "
                f"terminal {conflito['terminal']}: "
                f"{self.descrever_acao(conflito['acao_existente'])} x "
                f"{self.descrever_acao(conflito['nova_acao'])}"
            )

    def mostrar_tudo(self):
        self.mostrar_resumo()
        self.mostrar_action()
        self.mostrar_goto()
        self.mostrar_conflitos()

