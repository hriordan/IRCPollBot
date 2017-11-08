#! /usr/bin/env python
"""
IRC Vote/poll Bot.
An HRio Production.
"""

import re
import irc.bot
import irc.strings
from BotExceptions import BadVoteOption, BadPollIDValue


class Poll(object):
    # answers should be list of questions
    pollIDMaxLen = 10

    def __init__(self, question, pollID, creator, answers=[]):
        # TODO: associate poll with channel
        self.question = question
        self.pollID = pollID
        self.creator = creator
        self.answers = {}
        for num, answer in enumerate(answers, start=1):
            self.answers[num] = AnswerOption(answer, num)

    def addAnswer(self, answer):
        pass

    def voteForAnswer(self, answerEnum):
        # TODO: track if someone (by host) has already voted in a poll.
        answer = self.answers.get(answerEnum)
        if not answer:
            raise BadVoteOption
        answer.count += 1
        return answer

    def closePoll(self):
        """close a poll down. Don't delete contents."""
        pass


class AnswerOption(object):
    def __init__(self, answer, enumeration, count=0):
        self.answer = answer
        self.enumeration = enumeration
        self.count = count


class VoteBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, server, port=6667, nickname="VoteBot"):
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.polls = {}
        # TODO: save and load polls to db.

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def on_welcome(self, conn, event):
        # todo: make this listen on all channels?
        conn.join(self.channel)

    def on_join(self, conn, event):
        conn.notice(event.target, "Hi I'm a poll bot! Do .votebot help to find out about me.")

    def on_privmsg(self, conn, event):
        conn.privmsg(event.source.nick, "No private chat at the moment")

    def on_pubmsg(self, conn, event):
        # prefix should be in ".botname cmd" format
        arg = event.arguments[0].split(" ", 1)
        if len(arg) > 1 and arg[0].lower() == ('.%s' % self._nickname).lower():
            self.do_command(event, arg[1].strip())
        return

    def do_command(self, event, cmdInput):
        nick = event.source.nick
        target = event.target
        conn = self.connection

        # ideally in form cmd args
        inputs = cmdInput.split(' ', 1)
        cmd = inputs[0]
        if len(inputs) < 2:
            cmdArgs = None
        else:
            cmdArgs = inputs[1]

        # TODO: move this to dispatch table structure, moving all this stuff into own funcs
        if cmd == "createpoll":
            argsError = ("Not enough arguments supplied for createpoll cmd. Needs at least one answer supplied."
                         "pollID, question,answers must be in double quotes "
                         "Ex: .votebot createpoll \"bore\" \"who?\" \"ann?\" ")
            if not cmdArgs:
                conn.notice(target, argsError)
                return
            try:
                pollID, question, answers = self.parseCreatePollArgs(cmdArgs)
            except ValueError:
                conn.notice(target, argsError)
                return
            except BadPollIDValue as err:
                conn.notice(target, "Invalid Poll ID %s. Must be %s chars or fewer and not already in use" %
                                    (err.args[0], Poll.pollIDMaxLen))
                return

            self.handleCreatePoll(pollID, question, answers, nick)
            conn.notice(target, "I created a poll with ID %s" % pollID)
            self.displayPollInfo(target, pollID)

        elif cmd == "pollinfo":
            if not cmdArgs:
                conn.notice(target, "No arguments supplied for pollinfo cmd. Need a pollID")
                return
            pollID = self.parsePollInfoArgs(cmdArgs)
            self.displayPollInfo(target, pollID)

        elif cmd == "vote":
            if not cmdArgs:
                conn.notice(target, "No arguments supplied for vote cmd. Should <pollid> <answerNumber>")
                return
            try:
                pollID, voteAnswer = self.parseVoteArgs(cmdArgs)
            except ValueError:
                conn.notice(target, "Not enough arguments supplied for vote cmd. Should be <pollid> <answerNumber>")
                return
            except BadVoteOption:
                conn.notice(target, "Vote option must be an integer")
                return

            poll = self.polls.get(pollID)
            if not poll:
                conn.notice(target, "No such poll: %s" % pollID)
                return
            try:
                answer = poll.voteForAnswer(voteAnswer)
            except BadVoteOption:
                conn.notice(target, "no such option %d for poll %s" % (voteAnswer, pollID))
                return
            conn.notice(target, "Successful Vote. Option %d: '%s' now has %d votes." % (voteAnswer, answer.answer, answer.count))

        elif cmd == "list":
            self.listPolls(target)

        elif cmd == "help":
            conn.notice(target, "Commands are list, createpoll, vote, and pollinfo")
            # TODO: help responses for each command

        else:
            conn.notice(target, "Not understood: " + cmd)

    def handleCreatePoll(self, pollID, question, answers, creator):
        """register a poll to the polls dict."""
        newPoll = Poll(question, pollID, creator, answers)
        self.polls[pollID] = newPoll
        print("created poll %s" % pollID)

    def displayPollInfo(self, target, pollID):
        """msg channel/nick a given poll's info."""
        conn = self.connection
        try:
            poll = self.polls[pollID]
        except KeyError:
            conn.notice(target, "No such PollID %s" % pollID)
            return
        conn.notice(target,
                    "Poll ID: %(pollID)s - '%(question)s'. Options: " % {'pollID': pollID, 'question': poll.question})
        # get answers from poll
        for enum, answer in sorted(poll.answers.items(), key=lambda x: x[0]):
            conn.notice(target, " - %(enum)s: '%(answer)s', %(votes)s votes" % {'enum': enum,
                                                                                'answer': answer.answer,
                                                                                'votes': answer.count})

    def listPolls(self, channel):
        """list all available poll IDs to a given channel"""
        conn = self.connection
        if len(self.polls) == 0:
            conn.notice(channel, "No open polls.")
            return
        conn.notice(channel, "Open Polls:")
        for pollID in self.polls.keys():
            conn.notice(channel, "PollID %s: '%s'," % (pollID, self.polls[pollID].question))

    @staticmethod
    def parseVoteArgs(voteArgs):
        """should be in form <pollID> <answerEnum>"""
        parsedArgs = voteArgs.split()
        if len(parsedArgs) < 2:
            print("Not enough args for vote cmd")
            raise ValueError
        pollID = parsedArgs[0]
        try:
            ansEnum = int(parsedArgs[1])
        except ValueError:
            raise BadVoteOption
        return (pollID, int(ansEnum))

    @staticmethod
    def parsePollInfoArgs(infoArgs):
        """one argument, pollID"""
        return infoArgs.split()[0]

    def parseCreatePollArgs(self, pollArgs):
        """
        Poll args should come in form [pollID] [question] [options](variable #). They need to be quoted.
        Double quotes required, for now. Example: "time" "What time is it?" "3pm" "4pm" "midnight"
        """
        stringRegex = '"([^"]*)"'
        parsedArgs = re.findall(stringRegex, pollArgs)
        if len(parsedArgs) < 3:
            print("not enough args for createpoll cmd")  # switch to log
            raise ValueError
        pollID = parsedArgs[0]
        if len(pollID) > Poll.pollIDMaxLen or pollID in self.polls.keys():
            print("bad pollID")
            raise BadPollIDValue(pollID)
        question, answers = (parsedArgs[1], parsedArgs[2:])
        return (pollID, question, answers)


def main():
    debug = False # TODO: get from cmdline arg
    import sys
    if len(sys.argv) != 4:
        print("Usage: votebot <server[:port]> <channel>")
        sys.exit(1)
    print(sys.argv)
    sargs = sys.argv[1].split(":", 1)
    server = sargs[0]
    if len(sargs) == 2:
        try:
            port = int(sargs[1])
        except ValueError:
            print("Error: Erroneous port.")
            sys.exit(1)
    else:
        port = 6667
    channel = sys.argv[2]

    bot = VoteBot(channel, server, port)
    if not debug:
        while True:
            try:
                bot.start()
            except Exception as err:
                print("error!")
                print(err)
                print("restarting")
    else:
        bot.start()

if __name__ == "__main__":
    main()
