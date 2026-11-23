# ============================================================
# CÁLCULO DOS CONJUNTOS FIRST E FOLLOW
# ============================================================

EPSILON = "ε"
FIM_DA_ENTRADA = "$"


class FirstFollow:
    """
    Calcula os conjuntos FIRST e FOLLOW de uma gramática.

    A classe recebe uma instância de Gramatica e utiliza
    suas produções, seus terminais e seus não terminais.
    """

    def __init__(self, gramatica):
        self.gramatica = gramatica

        # Dicionários que armazenam os conjuntos calculados.
        # Exemplo: self.first["Expr"] = {"IDENTIFICADOR", "("}
        self.first = {}
        self.follow = {}

        # Inicializa um conjunto vazio para cada não terminal.
        for nao_terminal in self.gramatica.nao_terminais:
            self.first[nao_terminal] = set()
            self.follow[nao_terminal] = set()

        # Sinalizadores: só viram True depois que o cálculo termina.
        # Os dicionários acima já nascem preenchidos (com conjuntos
        # vazios), então NÃO dá para saber se o cálculo rodou olhando
        # se eles estão vazios. Quem precisa saber (ex.: a tabela SLR)
        # consulta a propriedade "calculado".
        self._first_pronto = False
        self._follow_pronto = False

    @property
    def calculado(self):
        """True somente se FIRST e FOLLOW já foram calculados."""
        return self._first_pronto and self._follow_pronto

    # ========================================================
    # 1. CÁLCULO DO FIRST
    # ========================================================

    def first_da_sequencia(self, sequencia):
        """
        Calcula o FIRST de uma sequência de símbolos.

        Exemplo:
            FIRST(("Expr", "+", "IDENTIFICADOR"))

        Retorna um conjunto de terminais e, se necessário,
        também o símbolo ε.
        """

        resultado = set()

        # Uma sequência vazia pode gerar ε.
        if not sequencia:
            return {EPSILON}

        # Percorre os símbolos da sequência da esquerda para a direita.
        for simbolo in sequencia:

            # Se for terminal, ele pode iniciar a sequência.
            if simbolo in self.gramatica.terminais:
                resultado.add(simbolo)
                return resultado

            # Se for não terminal, adicionamos seu FIRST,
            # mas sem o ε por enquanto.
            if simbolo in self.gramatica.nao_terminais:
                resultado.update(self.first[simbolo] - {EPSILON})

                # Se o não terminal não pode gerar ε,
                # não precisamos olhar os próximos símbolos.
                if EPSILON not in self.first[simbolo]:
                    return resultado

            else:
                raise ValueError(
                    f"Símbolo desconhecido na gramática: {simbolo}"
                )

        # Se todos os símbolos podem gerar ε,
        # a sequência inteira também pode.
        resultado.add(EPSILON)

        return resultado

    def calcular_first(self):
        """
        Calcula FIRST para todos os não terminais.

        O algoritmo repete as produções até que nenhum
        conjunto FIRST receba novos elementos.
        """

        houve_alteracao = True

        while houve_alteracao:
            houve_alteracao = False

            # Percorre todas as produções da gramática.
            for nao_terminal, alternativa in self.gramatica.lista_producoes:

                # Calcula o FIRST do lado direito da produção.
                novos_elementos = self.first_da_sequencia(alternativa)

                # Guarda a quantidade anterior de elementos.
                tamanho_anterior = len(self.first[nao_terminal])

                # Adiciona os novos elementos ao FIRST da regra.
                self.first[nao_terminal].update(novos_elementos)

                # Se o conjunto cresceu, precisamos repetir o algoritmo.
                if len(self.first[nao_terminal]) > tamanho_anterior:
                    houve_alteracao = True

        self._first_pronto = True

        return self.first

    # ========================================================
    # 2. CÁLCULO DO FOLLOW
    # ========================================================

    def calcular_follow(self):
        """
        Calcula FOLLOW para todos os não terminais.

        O algoritmo também repete as produções até que
        nenhum conjunto FOLLOW receba novos elementos.

        O FOLLOW depende do FIRST, então calcular_first() precisa
        ter rodado antes.
        """

        if not self._first_pronto:
            raise RuntimeError(
                "FOLLOW depende do FIRST. "
                "Execute calcular_first() (ou calcular()) primeiro."
            )

        # O símbolo inicial pode ser seguido pelo fim da entrada.
        self.follow[self.gramatica.simbolo_inicial].add(FIM_DA_ENTRADA)

        houve_alteracao = True

        while houve_alteracao:
            houve_alteracao = False

            # Percorre todas as produções A -> lado_direito.
            for nao_terminal, alternativa in self.gramatica.lista_producoes:

                # Percorre cada posição do lado direito.
                for i, simbolo in enumerate(alternativa):

                    # FOLLOW só é calculado para não terminais.
                    if simbolo not in self.gramatica.nao_terminais:
                        continue

                    # Pega tudo que vem depois do não terminal atual.
                    beta = alternativa[i + 1:]

                    # Calcula FIRST da sequência que vem depois.
                    first_beta = self.first_da_sequencia(beta)

                    # Regra 1:
                    # Adiciona FIRST(beta) - {ε} ao FOLLOW do símbolo.
                    novos_elementos = first_beta - {EPSILON}

                    tamanho_anterior = len(self.follow[simbolo])

                    self.follow[simbolo].update(novos_elementos)

                    # Regra 2:
                    # Se beta pode gerar ε (ou está vazia),
                    # adicionamos FOLLOW do lado esquerdo da produção.
                    if EPSILON in first_beta:
                        self.follow[simbolo].update(
                            self.follow[nao_terminal]
                        )

                    # Verifica se houve alguma mudança.
                    if len(self.follow[simbolo]) > tamanho_anterior:
                        houve_alteracao = True

        self._follow_pronto = True

        return self.follow

    # ========================================================
    # 3. EXECUÇÃO DOS DOIS CÁLCULOS
    # ========================================================

    def calcular(self):
        """
        Executa FIRST e FOLLOW na ordem correta.
        """

        self.calcular_first()
        self.calcular_follow()

        return self.first, self.follow

    # ========================================================
    # 4. EXIBIÇÃO DOS RESULTADOS
    # ========================================================

    def mostrar_first(self):
        print("\n========== CONJUNTOS FIRST ==========\n")

        for nao_terminal in sorted(self.first):
            elementos = sorted(self.first[nao_terminal])

            print(f"FIRST({nao_terminal}) = {{ {', '.join(elementos)} }}")

    def mostrar_follow(self):
        print("\n========== CONJUNTOS FOLLOW ==========\n")

        for nao_terminal in sorted(self.follow):
            elementos = sorted(self.follow[nao_terminal])

            print(f"FOLLOW({nao_terminal}) = {{ {', '.join(elementos)} }}")

    def mostrar_tudo(self):
        self.mostrar_first()
        self.mostrar_follow()
