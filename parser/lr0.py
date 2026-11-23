# ============================================================
# CONSTRUÇÃO DO AUTÔMATO LR(0)
# ============================================================


class AutomatoLR0:
    """
    Constrói automaticamente os estados e as transições
    do autômato LR(0) a partir de uma gramática.

    Cada item é representado por uma tupla:

        (nao_terminal, alternativa, posicao_do_ponto)

    Exemplo:

        ("DeclPacote", ("package", "IDENTIFICADOR", ";"), 1)

    Representa:

        DeclPacote -> package . IDENTIFICADOR ;
    """

    def __init__(self, gramatica):

        # Guardamos a gramática original.
        self.gramatica_original = gramatica

        # O LR(0) precisa trabalhar com a gramática aumentada.
        # Ela adiciona uma nova produção inicial:
        # Programa' -> Programa
        self.gramatica = gramatica.gramatica_aumentada()

        # Guardamos os símbolos da gramática aumentada.
        self.nao_terminais = self.gramatica.nao_terminais
        self.terminais = self.gramatica.terminais

        # Organizamos as produções por não terminal.
        #
        # Exemplo:
        # {
        #     "DeclPacote": [
        #         ("package", "IDENTIFICADOR", ";")
        #     ]
        # }
        #
        # Isso facilita encontrar as produções durante o closure.
        self.producoes_por_nao_terminal = {}

        for nao_terminal in self.nao_terminais:
            self.producoes_por_nao_terminal[nao_terminal] = (
                self.gramatica.producoes_de(nao_terminal)
            )

        # Lista de estados do autômato.
        # Cada estado será um conjunto de itens LR(0).
        self.estados = []

        # Dicionário de transições.
        #
        # Exemplo:
        # (0, "package"): 1
        #
        # Significa que do estado 0, ao avançar pelo
        # símbolo "package", chegamos ao estado 1.
        self.transicoes = {}

    # ========================================================
    # 1. OPERAÇÃO CLOSURE
    # ========================================================

    def closure(self, itens):
        """
        Calcula o fechamento de um conjunto de itens LR(0).

        Regra:
        Se o ponto estiver antes de um não terminal,
        adicionamos todas as produções desse não terminal
        com o ponto na primeira posição.
        """

        # Transformamos os itens em conjunto para evitar duplicatas.
        fechamento = set(itens)

        # Lista de itens que ainda precisam ser analisados.
        fila = list(itens)

        # Enquanto existirem itens para analisar...
        while fila:

            # Retiramos um item da fila.
            nao_terminal, alternativa, posicao = fila.pop()

            # Verificamos se o ponto já chegou ao final.
            if posicao >= len(alternativa):
                continue

            # Descobrimos qual símbolo está depois do ponto.
            proximo_simbolo = alternativa[posicao]

            # Se for um terminal, não precisamos expandir.
            if proximo_simbolo not in self.nao_terminais:
                continue

            # Se for um não terminal, precisamos adicionar
            # todas as suas produções com o ponto no início.
            for nova_alternativa in (
                self.producoes_por_nao_terminal[proximo_simbolo]
            ):

                novo_item = (
                    proximo_simbolo,
                    nova_alternativa,
                    0
                )

                # Só adicionamos se ainda não existir.
                if novo_item not in fechamento:

                    fechamento.add(novo_item)
                    fila.append(novo_item)

        return frozenset(fechamento)

    # ========================================================
    # 2. OPERAÇÃO GOTO
    # ========================================================

    def goto(self, estado, simbolo):
        """
        Calcula o estado alcançado ao avançar pelo símbolo.

        Para cada item que possui o símbolo depois do ponto,
        avançamos o ponto uma posição.

        Depois calculamos o closure dos novos itens.
        """

        novos_itens = set()

        # Percorremos todos os itens do estado atual.
        for nao_terminal, alternativa, posicao in estado:

            # Verificamos se ainda existe símbolo depois do ponto.
            if posicao < len(alternativa):

                # Verificamos se o próximo símbolo é o desejado.
                if alternativa[posicao] == simbolo:

                    # Avançamos o ponto uma posição.
                    novo_item = (
                        nao_terminal,
                        alternativa,
                        posicao + 1
                    )

                    novos_itens.add(novo_item)

        # Se nenhum item avançou, não existe transição.
        if not novos_itens:
            return frozenset()

        # O novo estado precisa ter seu fechamento calculado.
        return self.closure(novos_itens)

    # ========================================================
    # 3. CONSTRUÇÃO DOS ESTADOS LR(0)
    # ========================================================

    def construir(self):
        """
        Constrói todos os estados possíveis do autômato LR(0).

        Começa pelo fechamento do item inicial e vai
        descobrindo novos estados por meio de GOTO.
        """

        # Descobrimos o símbolo inicial da gramática aumentada.
        inicio = self.gramatica.simbolo_inicial

        # A gramática aumentada possui uma produção:
        # Programa' -> Programa
        producao_inicial = self.gramatica.producoes_de(inicio)[0]

        # Criamos o item inicial:
        # Programa' -> . Programa
        item_inicial = (inicio, producao_inicial, 0)

        # O primeiro estado é o fechamento do item inicial.
        estado_inicial = self.closure({item_inicial})

        # Começamos com apenas o estado 0.
        self.estados = [estado_inicial]

        # Mapeia cada estado para seu número.
        # Isso permite verificar rapidamente se um estado
        # já foi criado.
        indices_estados = {
            estado_inicial: 0
        }

        # Índice do estado que estamos analisando.
        indice_atual = 0

        # Analisamos os estados até não existirem novos.
        while indice_atual < len(self.estados):

            estado = self.estados[indice_atual]

            # Descobrimos todos os símbolos que aparecem
            # imediatamente depois do ponto nos itens do estado.
            simbolos = set()

            for nao_terminal, alternativa, posicao in estado:

                if posicao < len(alternativa):
                    simbolos.add(alternativa[posicao])

            # Ordenamos os símbolos para deixar a construção
            # dos estados mais previsível.
            for simbolo in sorted(simbolos):

                # Calculamos o estado alcançado pelo símbolo.
                novo_estado = self.goto(estado, simbolo)

                # Se não houver transição, seguimos para o próximo.
                if not novo_estado:
                    continue

                # Verificamos se esse estado já foi criado.
                if novo_estado not in indices_estados:

                    # Se não foi criado, adicionamos à lista.
                    novo_indice = len(self.estados)

                    self.estados.append(novo_estado)

                    indices_estados[novo_estado] = novo_indice

                else:
                    # Se já existe, recuperamos seu número.
                    novo_indice = indices_estados[novo_estado]

                # Registramos a transição.
                self.transicoes[(indice_atual, simbolo)] = novo_indice

            # Passamos para o próximo estado.
            indice_atual += 1

        return self.estados, self.transicoes

    # ========================================================
    # 4. FORMATAÇÃO DOS ITENS
    # ========================================================

    def formatar_item(self, item):
        """
        Transforma a representação interna de um item
        em texto legível, colocando o ponto na posição correta.
        """

        nao_terminal, alternativa, posicao = item

        # Copiamos os símbolos da produção.
        simbolos = list(alternativa)

        # Inserimos o ponto na posição indicada.
        simbolos.insert(posicao, "·")

        # Tratamento visual para produções vazias.
        if not alternativa:
            lado_direito = "·"
        else:
            lado_direito = " ".join(simbolos)

        return f"{nao_terminal} -> {lado_direito}"

    # ========================================================
    # 5. EXIBIÇÃO DOS ESTADOS
    # ========================================================

    def mostrar_estados(self):
        """
        Exibe todos os estados construídos pelo autômato.
        """

        print("\n========== ESTADOS LR(0) ==========\n")

        for indice, estado in enumerate(self.estados):

            print(f"Estado {indice}:")

            # Ordenamos os itens para facilitar a leitura.
            itens_ordenados = sorted(
                estado,
                key=lambda item: (
                    item[0],
                    item[1],
                    item[2]
                )
            )

            for item in itens_ordenados:
                print("   ", self.formatar_item(item))

            print()

    # ========================================================
    # 6. EXIBIÇÃO DAS TRANSIÇÕES
    # ========================================================

    def mostrar_transicoes(self):
        """
        Exibe todas as transições entre os estados.
        """

        print("\n========== TRANSIÇÕES LR(0) ==========\n")

        transicoes_ordenadas = sorted(
            self.transicoes.items(),
            key=lambda item: (item[0][0], item[0][1])
        )

        for (estado_origem, simbolo), estado_destino in (
            transicoes_ordenadas
        ):

            print(
                f"Estado {estado_origem}"
                f" -- {simbolo} --> "
                f"Estado {estado_destino}"
            )

    # ========================================================
    # 7. EXIBIÇÃO COMPLETA
    # ========================================================

    def mostrar_tudo(self):
        self.mostrar_estados()
        self.mostrar_transicoes()

