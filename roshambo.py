#!/usr/bin/python

import asyncio
import socket
import enum
import random

from contextlib import closing


class GameOver(Exception):
    pass


class Quit(Exception):
    pass


class Choice(int, enum.Enum):
    ROCK = 0
    PAPER = 1
    SCISSORS = 2


ChoiceMap = {
    Choice.ROCK: [Choice.PAPER, Choice.SCISSORS],
    Choice.PAPER: [Choice.SCISSORS, Choice.ROCK],
    Choice.SCISSORS: [Choice.ROCK, Choice.PAPER],
}


class Result(int, enum.Enum):
    LOSE = 0
    TIE = 1
    WIN = 2


class StringWriter:
    eol = b"\r\n"

    def __init__(self, writer):
        self.writer = writer

    def write(self, data):
        self.writer.write(data.encode())

    def writeline(self, data):
        self.write(data)
        self.writer.write(self.eol)

    def writelines(self, data):
        for line in data:
            self.writeline(line)

    async def drain(self):
        await self.writer.drain()


class Roshambo:
    def __init__(self, rounds=1):
        if rounds % 2 == 0:
            raise ValueError("rounds must be odd")

        self.rounds = rounds
        self.round = 0
        self.results: list[Result | None] = [None] * rounds
        self.they_win = False
        self.game_over = False

    def throw(self, theirs: Choice) -> tuple[Choice, Choice, Result, bool | None]:
        if self.game_over:
            raise GameOver()

        mine = random.choice(list(Choice))

        if mine == theirs:
            res = Result.TIE
        elif theirs == ChoiceMap[mine][0]:
            res = Result.WIN
        else:
            res = Result.LOSE

        self.results[self.round] = res
        self.round += 1

        if self.round >= self.rounds:
            self.game_over = True
            self.they_win = (
                len([x for x in self.results if x == Result.WIN]) > self.rounds // 2
            )

        return (theirs, mine, res, self.they_win)


async def one_round(game, reader, _writer):
    writer = StringWriter(_writer)
    writer.writelines(
        [
            ("*" * 70),
            "Round {game.round + 1}",
            ("*" * 70),
        ]
    )
    writer.writelines(
        [
            "0 - Rock",
            "1 - Paper",
            "2 - Scissors",
        ]
    )
    await writer.drain()

    while True:
        writer.write("Enter a choice [0-2]: ")
        await writer.drain()
        raw_choice = await reader.readline()
        if raw_choice.decode().strip() == "q":
            raise Quit()

        try:
            choice = Choice(int(raw_choice))
            res = game.throw(choice)
            writer.writelines(
                [
                    f"You chose: {res[0].name}",
                    f"Computer chose: {res[1].name}",
                ]
            )

            if res[2] == Result.TIE:
                writer.writeline("This round is tied.")
            elif res[2] == Result.WIN:
                writer.writeline("You won this round.")
            else:
                writer.writeline("You lost this round.")
            await writer.drain()
            break
        except ValueError as err:
            writer.writeline(f"Invalid choice: {err}")
            await writer.drain()


async def roshambo_client(reader, writer):
    game = Roshambo(rounds=3)

    with closing(writer):
        try:
            while not game.game_over:
                await one_round(game, reader, writer)

            if game.they_win:
                msg = "You won the game!"
            else:
                msg = "You lost the game!"
        except Quit:
            msg = "Giving up?"
        except UnicodeDecodeError:
            return
        except ConnectionResetError:
            return

        writer.write(msg.encode())
        writer.write(b"\r\n")
        await writer.drain()


async def main():
    server = await asyncio.start_server(roshambo_client, port=5000)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
