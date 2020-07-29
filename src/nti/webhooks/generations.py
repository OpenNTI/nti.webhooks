# -*- coding: utf-8 -*-
"""
    - We have an IInstallableSchemaManager global utility. ZCML
      directives register their arguments with this utility.

    - An AfterDatabaseOpened handler reads data from the root of the
      database about what is currently installed and calculates the
      difference.

      This information is used to calculate the generation we should use for
      the schema manager. It needs to handle initial installation of
      everything as well as adding and removing.

    - When AfterDatabaseOpenedWithRoot fires, our schema manager,
      which should be named so as to sort near the end, runs and
      performs required changes, recording what is actually installed
      in the root of the database.

While this might seem limited to one application or root per database,
it shouldn't be. The ZCML directives will include the full traversable
path to a site manager, starting from the root.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
