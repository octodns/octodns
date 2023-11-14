### This is all a WIP

This is a WIP and will definitely be rough around the edges, but in the spirit
of not letting perfect get in the way of good enough, or really existing at
all. It's being uploaded as a starting point. PRs/suggestions welcome as are
ideas for other subjects to cover.

### Examples

* Getting started with a [basic octoDNS configuration](basic/) - new to octoDNS
  this is the place to start. It'll walk you through the main pieces of DNS IaC
  with octoDNS including the process of planning and applying changes.
* [Migrating to octoDNS](migrating-to-octodns/) - have an existing DNS setup
  you'd like to bring into octoDNS check this example out right after
  [basic](basic/). It'll walk you through the steps of using `octodns-dump` to
  pull the existing data out of your provider into matching YAML config files on
  disk.

### Running PowerDNS

If you'd like to play around with running the examples in this directory
interactively you'll need a target for pushing data to.
[octodns-powerdns](https://github.com/octodns/octodns-powerdns) is the best
stand-alone option for this and the examples directory makes extensive use of
it. There is a [docker-compose.yml](docker-compose.yml) file that should get a
fully functional copy of PowerDNS backed my MySQL with the API enabled along
with other relivant functionality. For any of the examples that refer to the
local PowerDNS instance the following instructions below should get it up and
running.

1. If you haven't already [install docker compose](https://docs.docker.com/compose/install/)
1. If you don't already have a copy of octoDNS checked out run `git clone https://github.com/octodns/octodns.git`
1. In a seperate terminal window or tab
1. cd into the examples directory `cd octodns/examples`
1. Run docker-compose up `docker-compose up`, this will start up MySQL and PowerDNS running them in the foreground with their logs printing to the terminal
